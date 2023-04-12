import os
import pendulum
from datetime import timedelta

from airflow import DAG
from airflow.decorators import task

DEFAULT_ARGS = {
    'owner': 'AlertaDengue',
    'depends_on_past': False,
    # 'email': [email_main],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}

env = os.getenv
email_main = env('EMAIL_MAIN')
DATA_DIR = '/tmp/copernicus'
PG_URI_MAIN = (
    'postgresql://'
    f"{env('PSQL_USER_MAIN')}"
    f":{env('PSQL_PASSWORD_MAIN')}"
    f"@{env('PSQL_HOST_MAIN')}"
    f":{env('PSQL_PORT_MAIN')}"
    f"/{env('PSQL_DB_MAIN')}"
)
CDSAPI_KEY = env('CDSAPI_KEY')

with DAG(
    dag_id='COPERNICUS_BRASIL',
    description='ETL of weather data for Brazil',
    tags=['Brasil', 'Copernicus'],
    schedule='@daily',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2000, 1, 9),
    catchup=False, #TODO CHANGE TO TRUE
    max_active_runs=8,
):

    DATE = '{{ ds }}'

    @task.external_python(
        task_id="daily_fetch", 
        python="/opt/py310/bin/python3.10"
    )
    def extract_transform_load(
        date: str, 
        data_dir: str, 
        api_key: str, 
        psql_uri: str
    ) -> None:
        from pathlib import Path
        from dateutil import parser
        from datetime import timedelta
        from sqlalchemy import create_engine
        from satellite import weather as sat_w
        from satellite import downloader as sat_d
        from satellite.weather._brazil.extract_latlons import MUNICIPIOS

        try:
            with create_engine(psql_uri).connect() as conn:
                cur = conn.execute(
                    f"SELECT DISTINCT(date) FROM weather.copernicus_brasil"
                )
                dates = cur.all()
        except Exception as e:
            if 'UndefinedTable' in str(e):
                print("First insertion")
                dates = []
            else:
                raise e

        if date in dates:
            print(f'[INFO] {date} has been fetched already.')
            return None

        start_date = parser.parse(str(date)).date()
        max_update_delay = start_date - timedelta(days=9)

        netcdf_file = sat_d.download_br_netcdf(
            date=str(max_update_delay),
            data_dir=data_dir,
            user_key=api_key
        )
        filepath = Path(data_dir) / netcdf_file

        ds = sat_w.load_dataset(filepath)
        geocodes = [mun['geocodigo'] for mun in MUNICIPIOS]

        df = ds.copebr.to_dataframe(geocodes, raw=False)

        with create_engine(psql_uri).connect() as conn:
            df.to_sql(
                name='copernicus_brasil',
                schema='weather',
                con=conn,
                if_exists='append',
            )

        Path(filepath).unlink(missing_ok=False)

    ETL = extract_transform_load(DATE, DATA_DIR, CDSAPI_KEY, PG_URI_MAIN)

    ETL
