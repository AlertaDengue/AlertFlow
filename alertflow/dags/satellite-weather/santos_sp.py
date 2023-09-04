"""
Author: Luã Bida Vacaro
Email: luabidaa@gmail.com
Github: https://github.com/luabida
Date: 2023-09-04

The COPERNICUS_SANTOS Airflow DAG will retrieve daily weather data
for the Brazilian city of Santos, SP by accessing the Copernicus
ERA5 Reanalysis dataset. This climate information includes temperature,
precipitation, humidity, and atmospheric pressure, which is collected
every 3 hours daily from January 1st, 2000 to the present. For safety
measures, the DAG is programmed to have a 9-day delay from the current
date, considering that the Copernicus API typically takes an average
of 7 days to update the dataset.
"""
import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.models import Variable

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
KEY = Variable.get('cdsapi_key', deserialize_json=True)
URI = Variable.get('psql_main_uri', deserialize_json=True)

with DAG(
    dag_id='COPERNICUS_SANTOS',
    description='ETL of weather data for Santos, SP - BR',
    tags=['Brasil', 'Copernicus', 'Santos'],
    schedule='@daily',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2018, 1, 9),
    catchup=True,
    max_active_runs=15,
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
        from pathlib import Path

        from dateutil import parser
        from satellite import downloader as sat_d
        from satellite import weather as sat_w
        from sqlalchemy import create_engine

        exec_date = parser.parse(str(date)).date()
        max_update_delay = exec_date - timedelta(days=9)

        try:
            # Check if date has been already inserted
            with create_engine(psql_uri['PSQL_MAIN_URI']).connect() as conn:
                cur = conn.execute(
                    'SELECT geocodigo FROM weather.copernicus_santos_sp'
                    f" WHERE date = '{str(max_update_delay)}'"
                )
                inserted = any(cur.fetchall())
        except Exception as e:
            if 'UndefinedTable' in str(e):
                print('First insertion')
                dates = []
            else:
                raise e

        if inserted:
            return f"Data for {date} has been fetched already"

        def format_date(dt: datetime):
            return dt.strftime('%F')

        # Downloads the NetCDF4 dataset
        netcdf_file = sat_d.download_netcdf(
            date=str(max_update_delay),
            data_dir=data_dir,
            area={"N": -23.75, "W": -46.5, "S": -24.25, "E": -46.0},
            user_key=api_key['CDSAPI_KEY'],
            filename=f"santos_{str(max_update_delay)}"
        )
        filepath = Path(data_dir) / netcdf_file

        # Reads the dataset
        ds = sat_w.load_dataset(filepath)

        # Transform the data, returns a pandas DataFrame
        df = ds.copebr.to_dataframe(3548500)

        # Insert the DataFrame into DB
        with create_engine(psql_uri['PSQL_MAIN_URI']).connect() as conn:
            df.to_sql(
                name='copernicus_santos_sp',
                index=False,
                schema='weather',
                con=conn,
                if_exists='append',
            )
        print(f'{filepath} inserted into weather.copernicus_santos_sp')

        # Deletes the dataset
        Path(filepath).unlink(missing_ok=True)

    # Instantiate the Task
    ETL = extract_transform_load(DATE, DATA_DIR, KEY, URI)

    ETL   # Execute
