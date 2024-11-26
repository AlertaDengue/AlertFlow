"""
Author: Luã Bida Vacaro
Email: luabidaa@gmail.com
Github: https://github.com/luabida
Date: 2023-04-13

The COPERNICUS_BRASIL Airflow DAG will collect daily weather
data from the Copernicus ERA5 Reanalysis dataset for all 5570
cities in Brazil. This data includes temperature, precipitation,
humidity, and atmospheric pressure, which is collected daily
starting from January 1st, 2000 to the present day.

To ensure reliability and safety, the DAG has a 9-day delay
from the current date, as the Copernicus API usually takes
around 7 days to update the dataset.
"""

import os
from pathlib import Path
from datetime import date, timedelta
from itertools import chain

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from satellite import ADM2, request
from sqlalchemy import create_engine, text

env = os.getenv
email_main = env("EMAIL_MAIN")

DEFAULT_ARGS = {
    "owner": "AlertaDengue",
    "depends_on_past": False,
    # 'email': [email_main],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 5,
    "retry_delay": timedelta(seconds=30),
}


with DAG(
    dag_id="COPERNICUS_BRASIL",
    description="ETL of weather data for Brazil",
    tags=["Brasil", "Copernicus"],
    schedule="@monthly",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2000, 1, 1),
    catchup=True,
    max_active_runs=14,
) as dag:
    DATE = "{{ ds }}"  # DAG execution date
    KEY = Variable.get("cdsapi_key", deserialize_json=True)
    URI = Variable.get("psql_main_uri", deserialize_json=True)

    @task
    def fetch_ds(locale, dt, uri, api_key):
        tablename = f"copernicus_{locale.lower()}"
        engine = create_engine(uri)
        dt = date.fromisoformat(dt) - timedelta(days=5)

        with engine.connect() as conn:
            cur = conn.execute(
                text(
                    f"SELECT geocode FROM weather.{tablename}"
                    f" WHERE date = '{str(dt)}'"
                )
            )
            table_geocodes = set(chain(*cur.fetchall()))

        all_geocodes = set([adm.code for adm in ADM2.filter(adm0=locale)])
        geocodes = all_geocodes.difference(table_geocodes)
        print("TABLE_GEO ", f"[{len(table_geocodes)}]: ", table_geocodes)
        print("DIFF_GEO: ", f"[{len(geocodes)}]: ", geocodes)

        basename = str(dt).replace("-", "_") + locale
        with request.reanalysis_era5_land(
            basename,
            api_token=api_key,
            date=str(dt),
            locale=locale,
        ) as ds:
            for geocode in geocodes:
                adm = ADM2.get(code=geocode):
                with engine.connect() as conn:
                    ds.cope.to_sql(adm, conn, tablename, "weather")
            file = Path(f"{basename}.zip")
            if file.exists():
                file.unlink()
                print(f"{file} removed")

    fetch_ds("BRA", DATE, URI["PSQL_MAIN_URI"], KEY["CDSAPI_KEY"])
