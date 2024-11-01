"""
Author: Luã Bida Vacaro
Email: luabidaa@gmail.com
Github: https://github.com/luabida
Date: 2023-04-13

The COPERNICUS_ARG Airflow DAG will collect daily weather
data from the Copernicus ERA5 Land Reanalysis dataset for all
cities in Argentina. This data includes temperature, precipitation,
humidity, and atmospheric pressure, which is collected daily
starting from January 1st, 2000 to the present day.

To ensure reliability and safety, the DAG has a 9-day delay
from the current date, as the Copernicus API usually takes
around 7 days to update the dataset.
"""

import os
import logging
import calendar
from datetime import timedelta, date

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable
from sqlalchemy import create_engine, text

from satellite import request, ADM2

env = os.getenv
email_main = env("EMAIL_MAIN")

DEFAULT_ARGS = {
    "owner": "AlertaDengue",
    "depends_on_past": False,
    # 'email': [email_main],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
}



with DAG(
    dag_id="COPERNICUS_ARG",
    description="ETL of weather data for Brazil",
    tags=["Argentina", "Copernicus"],
    schedule="@monthly",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2000, 1, 1),
    end_date=pendulum.datetime(2024, 1, 1),
    catchup=True,
    max_active_runs=14,
) as dag:
    DATE = "{{ ds }}"  # DAG execution date
    KEY = Variable.get("cdsapi_key", deserialize_json=True)
    URI = Variable.get("psql_main_uri", deserialize_json=True)

    @task
    def fetch_ds(dt, uri, api_key):
        locale = "ARG"
        tablename = f"copernicus_{locale.lower()}"
        engine = create_engine(uri)
        dt = date.fromisoformat(dt)
        end_day = calendar.monthrange(dt.year, dt.month)[1]
        date_str = f"{dt.replace(day=1)}/{dt.replace(day=end_day)}"
        # with engine.connect() as conn:
        #     cur = conn.execute(
        #         text(
        #             f"SELECT geocode FROM weather.{tablename}"
        #             f" WHERE date = '{dt}'"
        #         )
        #     )
        #     table_geocodes = set(chain(*cur.fetchall()))
        #
        # all_geocodes = set([adm.code for adm in ADM2.filter(adm0=locale)])
        # geocodes = all_geocodes.difference(table_geocodes)
        # print("TABLE_GEO ", f"[{len(table_geocodes)}]: ", table_geocodes)
        # print("DIFF_GEO: ", f"[{len(geocodes)}]: ", geocodes)

        with request.reanalysis_era5_land(
            date_str.replace("/", "_") + locale,
            api_token=api_key,
            date=date_str,
            locale=locale,
        ) as ds:
            for adm in ADM2.filter(adm0=locale):
                with engine.connect() as conn:
                    ds.cope.to_sql(adm, conn, tablename, "weather")

    fetch_ds(DATE, URI["PSQL_MAIN_URI"], KEY["CDSAPI_KEY"])
