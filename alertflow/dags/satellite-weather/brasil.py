"""
ᆖλᆖᆖᆖᆖᆖᆖᆖᆖᆖλᆖᆖᆖᆖᆖᆖᆖᆖᆖλᆖ
Author: Luã Bida Vacaro
Email: luabidaa@gmail.com
Github: https://github.com/luabida
Date: 2023-04-13
ᆖλᆖᆖᆖᆖᆖᆖᆖᆖᆖλᆖᆖᆖᆖᆖᆖᆖᆖᆖλᆖ

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
from datetime import timedelta

import pendulum
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
    catchup=True,
    max_active_runs=8,
):

    DATE = '{{ ds }}'   # DAG execution date

    @task.external_python(
        task_id='daily_fetch', python='/opt/py310/bin/python3.10'
    )
    def extract_transform_load(
        date: str, data_dir: str, api_key: str, psql_uri: str
    ) -> None:
        """
        Due to incompatibility issues between Airflow's Python version
        and the satellite-weather-downloader (SWD) package, this task
        will be executed in a dedicated virtual environment, which
        includes a pre-installed Python3.10 interpreter within the
        container. All imports must be within the scope of the task,
        and XCom sharing between tasks is not allowed.

        The task is designed to receive the execution date and download
        the weather dataset for that specific day. After downloading,
        the data is transformed using Xarray and inserted into the Main
        Postgres DB, as specified in the .env file, in the form of a
        DataFrame containing the weather information.
        """
        from datetime import datetime, timedelta
        from itertools import chain
        from pathlib import Path

        from dateutil import parser
        from satellite import downloader as sat_d
        from satellite import weather as sat_w
        from satellite.weather._brazil.extract_latlons import MUNICIPIOS
        from sqlalchemy import create_engine

        def format_date(dt: datetime):
            return dt.strftime('%F')

        def is_date_in_db(date: str) -> bool:
            # Checks if date has been already inserted into DB
            try:
                with create_engine(psql_uri).connect() as conn:
                    cur = conn.execute(
                        'SELECT DISTINCT(date::DATE)'
                        ' FROM weather.copernicus_brasil'
                    )
                    dates = list(chain(*cur.all()))
            except Exception as e:
                if 'UndefinedTable' in str(e):
                    # For dev purposes, in case table was not found
                    print('First insertion')
                    dates = []
                else:
                    raise e

            if str(date) in list(map(format_date, dates)):
                return True
            return False

        start_date = parser.parse(str(date)).date()
        max_update_delay = start_date - timedelta(days=9)

        if is_date_in_db(date=format_date(max_update_delay)):
            print(f'[INFO] {date} has been fetched already.')
            return None

        # Downloads daily dataset
        netcdf_file = sat_d.download_br_netcdf(
            date=str(max_update_delay), data_dir=data_dir, user_key=api_key
        )
        filepath = Path(data_dir) / netcdf_file
        print(f'[INFO] Handling {filepath}')

        # Reads the NetCDF4 file using Xarray
        ds = sat_w.load_dataset(filepath)
        geocodes = [mun['geocodigo'] for mun in MUNICIPIOS]

        # Transforms the data into Pandas DataFrame
        df = ds.copebr.to_dataframe(geocodes, raw=False)

        # Inserts weather data into DB
        with create_engine(psql_uri).connect() as conn:
            if is_date_in_db(date=format_date(max_update_delay)):
                # Second assertion in case file is being handle twice
                print(f'[INFO] {date} has been fetched already.')
                return None

            df.to_sql(
                name='copernicus_brasil',
                schema='weather',
                con=conn,
                if_exists='append',
            )

        # Deletes the NetCDF4 file
        Path(filepath).unlink(missing_ok=True)

    # Instantiate the Task
    ETL = extract_transform_load(DATE, DATA_DIR, CDSAPI_KEY, PG_URI_MAIN)

    ETL   # Execute
