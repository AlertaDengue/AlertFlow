"""
ERA5-Land daily weather ingestion for Brazil.

Runs daily with a 5-day delay. Data goes into weather.copernicus_bra.
"""

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from sqlalchemy import create_engine, text

_UNFILLABLE = {"2916104", "2919926", "2605459"}
_TABLE = "copernicus_bra"

DEFAULT_ARGS = {
    "owner": "AlertaDengue",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 5,
    "retry_delay": timedelta(seconds=60),
}

with DAG(
    dag_id="COPERNICUS_BRASIL",
    description="ETL of ERA5-Land weather data for Brazil",
    tags=["Brasil", "Copernicus"],
    schedule="@daily",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2026, 8, 1),
    catchup=True,
    max_active_runs=4,
) as dag:

    @task
    def fetch_weather(dt: str, **context):
        from satellite import ADM2, request

        eng_var = Variable.get("psql_main_uri", deserialize_json=True)
        uri = eng_var["PSQL_MAIN_URI"]
        key_var = Variable.get("cdsapi_key", deserialize_json=True)
        api_key = key_var["CDSAPI_KEY"]
        engine = create_engine(uri)

        day = date.fromisoformat(dt) - timedelta(days=5)

        print(f"[{day}] building GeoDataFrame...")
        _a = ADM2.filter(adm0="BRA")
        adms = [a for a in _a if str(a.code) not in _UNFILLABLE]
        gdf = pd.concat([a.to_dataframe() for a in adms], ignore_index=True)
        print(f"[{day}] {len(adms)} municipalities loaded")

        print(f"[{day}] downloading...")
        with request.reanalysis_era5_land(
            str(day).replace("-", "_"),
            api_token=api_key,
            date=str(day),
            locale="BRA",
        ) as ds:
            print(f"[{day}] processing (batch_to_df)...")
            df = ds.cope.batch_to_df(gdf, exclude_geocodes=_UNFILLABLE)

        if df.empty:
            print(f"[{day}] no data produced")
            return

        print(f"[{day}] inserting {len(df)} rows...")
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"""
                INSERT INTO weather.{_TABLE}
                    (date, geocode, epiweek,
                     temp_min, temp_med, temp_max,
                     precip_min, precip_med, precip_max, precip_tot,
                     pressao_min, pressao_med, pressao_max,
                     umid_min, umid_med, umid_max)
                VALUES (:date, :geocode, :epiweek,
                        :temp_min, :temp_med, :temp_max,
                        :precip_min, :precip_med, :precip_max, :precip_tot,
                        :pressao_min, :pressao_med, :pressao_max,
                        :umid_min, :umid_med, :umid_max)
                ON CONFLICT (date, geocode) DO UPDATE SET
                    precip_min = EXCLUDED.precip_min,
                    precip_med = EXCLUDED.precip_med,
                    precip_max = EXCLUDED.precip_max,
                    precip_tot = EXCLUDED.precip_tot
            """
                ),
                df.to_dict("records"),
            )
            conn.commit()

        print(f"[{day}] done: {len(df)} rows inserted/updated")

        file = Path(f"{str(day).replace('-', '_')}BRA.zip")
        if file.exists():
            file.unlink()

    fetch_weather("{{ ds }}")
