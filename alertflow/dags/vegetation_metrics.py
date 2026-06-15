from datetime import datetime, timedelta
import logging
from airflow.decorators import dag, task
from airflow.models import Variable
import geopandas as gpd

# Assume your original script functions are imported from an accessible module
# e.g., from geospatial_pipeline.core import carregar_municipios, parse_ufs, preparar_estado, processar_estado, definir_tabela, criar_tabela
# For the sake of this DAG, we assume those functions are available.

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


@dag(
    default_args=default_args,
    schedule_interval="@monthly",
    catchup=False,
    tags=["geospatial", "modis", "stac"],
    max_active_runs=1,
)
def vegetation_metrics_pipeline():

    @task
    def initialize_database():
        from sqlalchemy import create_engine, MetaData

        db_uri = Variable.get("GEOSPATIAL_DB_URI")
        table_name = Variable.get("GEOSPATIAL_TABLE_NAME", "vegetation_index_metrics")

        engine = create_engine(db_uri, pool_pre_ping=True)
        try:
            metadata = MetaData()
            tabela = definir_tabela(metadata, table_name)
            criar_tabela(engine, tabela)
        finally:
            engine.dispose()
        return table_name

    @task
    def extract_and_prepare_ufs(table_name: str):
        db_uri = Variable.get("GEOSPATIAL_DB_URI")
        collection = Variable.get("GEOSPATIAL_COLLECTION", "myd13q1-6.1")
        cache_path = Variable.get(
            "GEOSPATIAL_CACHE_MALHA", "cache/municipios_br_2020.gpkg"
        )
        uf_restriction = Variable.get("GEOSPATIAL_UF_RESTRICTION", None)

        from sqlalchemy import create_engine, MetaData

        engine = create_engine(db_uri, pool_pre_ping=True)
        metadata = MetaData()
        tabela = definir_tabela(metadata, table_name)

        munis = carregar_municipios(cache_path)
        ufs_to_process = parse_ufs(uf_restriction, munis)

        # In a real Airflow deployment, you can use logical_date to determine year/month dynamically
        # For example: year = {{ logical_date.year }}, month = {{ logical_date.month }}
        # Here we default to scanning full history or targeted intervals
        year = None
        month = None
        start_year = 2010

        prepaired_jobs = []

        # Simple non-grouped staging loop just to prepare metadata parameters for downstream workers
        for uf in ufs_to_process:
            munis_estado = munis[munis["uf"] == uf].copy()
            if munis_estado.empty:
                continue

            # We fetch STAC items and filter missing dates per state
            estado_info = preparar_estado(
                engine=engine,
                tabela=tabela,
                collection=collection,
                uf=uf,
                munis_estado=munis_estado,
                munis_download=munis_estado,
                year=year,
                month=month,
                start_year=start_year,
            )

            # Only queue states that actually have missing dates to process
            if "faltantes" in estado_info and estado_info["faltantes"]:
                # Serialization note: To pass data between tasks via XCom,
                # convert GeoDataFrames/complex objects into JSON-serializable dictionaries or paths.
                # For simplicity, we pass structural parameters:
                prepaired_jobs.append(
                    {
                        "uf": uf,
                        "collection": collection,
                        "table_name": table_name,
                        # Pass identifiers or reference metadata needed by the compute task
                    }
                )

        engine.dispose()
        return prepaired_jobs

    @task
    def process_individual_uf(job_info: dict):
        if not job_info:
            return "No work needed"

        db_uri = Variable.get("GEOSPATIAL_DB_URI")
        cache_path = Variable.get(
            "GEOSPATIAL_CACHE_MALHA", "cache/municipios_br_2020.gpkg"
        )

        from sqlalchemy import create_engine, MetaData

        engine = create_engine(db_uri, pool_pre_ping=True)
        metadata = MetaData()
        tabela = definir_tabela(metadata, job_info["table_name"])
        engine.dispose()  # processar_estado manages its own internal lifecycle

        # Re-load or re-construct required slices inside the isolated task worker
        munis = carregar_municipios(cache_path)
        munis_estado = munis[munis["uf"] == job_info["uf"]].copy()

        # Re-fetch state context parameters inside the worker
        # Alternatively, cache 'preparar_estado' outputs to an intermediate storage (like S3/GCS)
        # instead of passing raw structures via XCom.
        year = None
        month = None
        start_year = 2010

        # Re-run preparation inside worker to fetch active targets cleanly
        engine_worker = create_engine(db_uri, pool_pre_ping=True)
        prep = preparar_estado(
            engine=engine_worker,
            tabela=tabela,
            collection=job_info["collection"],
            uf=job_info["uf"],
            munis_estado=munis_estado,
            munis_download=munis_estado,
            year=year,
            month=month,
            start_year=start_year,
        )
        engine_worker.dispose()

        if not prep.get("faltantes"):
            return f"UF={job_info['uf']} already up to date"

        resultado = processar_estado(
            database_uri=db_uri,
            tabela=tabela,
            collection=job_info["collection"],
            uf=prep["uf"],
            munis_download=prep["munis_download"],
            urls_by_date=prep["urls_by_date"],
            atributos_por_data=prep["atributos_por_data"],
            faltantes=prep["faltantes"],
        )
        return resultado

    table_name_init = initialize_database()
    jobs = extract_and_prepare_ufs(table_name_init)
    # Dynamic Task Mapping: Spawns one isolated task instance per state job in parallel
    process_individual_uf.expand(job_info=jobs)


vegetation_dag = "vegetation_metrics_pipeline"()
