import re
import os
import sys
import pendulum
from dateutil import parser
from datetime import timedelta
from pathlib import Path, PosixPath
from sqlalchemy import create_engine

from airflow import DAG
from airflow.decorators import task
from airflow.operators.python import PythonVirtualenvOperator

env = os.getenv
email_main = env('EMAIL_MAIN')
DATA_DIR = '/tmp/copernicus'
DEFAULT_ARGS = {
    'owner': 'AlertaDengue',
    'depends_on_past': False,
    # 'email': [email_main],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}


PG_URI_MAIN = (
    'postgresql://'
    f"{env('PSQL_USER_MAIN')}"
    f":{env('PSQL_PASSWORD_MAIN')}"
    f"@{env('PSQL_HOST_MAIN')}"
    f":{env('PSQL_PORT_MAIN')}"
    f"/{env('PSQL_DB_MAIN')}"
)
TABLE_NAME = 'copernicus_brasil'
SCHEMA = 'weather'


with DAG(
    dag_id='COPERNICUS_BRASIL',
    description='ETL of weather data for Brazil',
    tags=['Brasil', 'Copernicus'],
    schedule='@daily',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2000, 1, 9),
    catchup=False, #TODO CHANGE TO TRUE
):

    E = PythonVirtualenvOperator(
        task_id='extract',
        python_callable=download_netcdf,
        requirements=["satellite-weather-downloader>=1.8.0"], 
        python_version='/opt/py310/bin/python3.10',
        expect_airflow=False,
        system_site_packages=False,
        # op_kwargs={'ini_date': '{{ ds }}'}
    )

    @task.virtualenv(
        task_id="loading", 
        requirements=["satellite-weather-downloader>=1.8.0"], 
        python_version='/opt/py310/bin/python3.10',
        expect_airflow=False,
        system_site_packages=False
    )
    def extract_load_clean(**context) -> None:
        """
        Reads the NetCDF file and generate the dataframe for all
        geocodes from IBGE using XArray and insert every geocode
        into postgres database.
        """
        from satellite import downloader as sat_d
    #     from satellite import weather as sat_w
    #     from satellite.weather._brazil.extract_latlons import MUNICIPIOS

    #     ti = context['ti']
    #     file = ti.xcom_pull(task_ids='extract')

    #     start_date = parser.parse(str(ini_date)).date()
    #     max_update_delay = start_date - timedelta(days=9)

    #     try:
    #         netcdf_file = sat_d.download_br_netcdf(
    #             date=str(max_update_delay), data_dir=DATA_DIR
    #         )
    #         filepath = Path(DATA_DIR) / netcdf_file
    #     except Exception as e:
    #         raise e

    #     ds = sat_w.load_dataset(file)
    #     geocodes = [mun['geocodigo'] for mun in MUNICIPIOS]

    #     df = ds.copebr.to_dataframe(geocodes, raw=False)

    #     with create_engine(PG_URI_MAIN).connect() as conn:
    #         df.to_sql(
    #             name=TABLE_NAME,
    #             schema=SCHEMA,
    #             con=conn,
    #             if_exists='append',
    #         )

    # @task(task_id='clean')
    # def remove_netcdf(**context):
    #     """Remove the file downloaded by extract task"""
    #     ti = context['ti']
    #     file = ti.xcom_pull(task_ids='extract')
    #     Path(file).unlink(missing_ok=False)

    # # Creating the tasks
    # TL = upload_dataset()
    # clean = remove_netcdf()

    # # Task flow
    # E >> TL >> clean
