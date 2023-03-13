import os
import pendulum

from dateutil import parser
from pathlib import Path, PosixPath
from sqlalchemy import create_engine
from datetime import datetime, timedelta

import satellite_weather as sat_w
import satellite_downloader as sat_d
from satellite_weather._brazil.extract_latlons import MUNICIPIOS

from airflow import DAG
from airflow.decorators.python import python_task
from airflow.operators.python import PythonOperator

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

UID = env('CDSAPI_UID')
KEY = env('CDSAPI_KEY')

PG_URI_MAIN = (
    'postgresql://'
    f"{env('PSQL_USER_MAIN')}"
    f":{env('PSQL_PASSWORD_MAIN')}"
    f"@{env('PSQL_HOST_MAIN')}"
    f":{env('PSQL_PORT_MAIN')}"
    f"/{env('PSQL_DB_MAIN')}"
)


with DAG(
    dag_id='COPERNICUS_BRASIL',
    description='ETL of weather data for Brazil',
    tags=['Brasil', 'Copernicus'],
    schedule='@daily',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2000, 1, 1),
    catchup=False,
):

    def download_netcdf(ini_date: str) -> PosixPath:
        start_date = parser.parse(str(ini_date)).date()
        max_update_delay = start_date - timedelta(days=9)

        try:
            netcdf_file = sat_d.download_br_netcdf(
                date=str(max_update_delay),
                date_end=None,
                data_dir=DATA_DIR,
                uid=UID,
                key=KEY,
            )
            filepath = Path(DATA_DIR) / netcdf_file
            return filepath
        except Exception as e:
            raise e

    E = PythonOperator(
        task_id='extract',
        python_callable=download_netcdf,
        op_kwargs={'ini_date': '{{ execution_date.strftime("%Y-%m-%d") }}'},
    )

    @python_task(task_id='loading')
    def upload_dataset(**context) -> PosixPath:
        ti = context['ti']
        file = ti.xcom_pull(task_ids='extract')
        ds = sat_w.load_dataset(file)
        for mun in MUNICIPIOS:
            df = ds.copebr.to_dataframe(mun['geocodigo'], raw=True)
            df.to_sql(
                name='copernicus_brasil',
                schema='weather',
                con=create_engine(PG_URI_MAIN),
            )
        return file

    @python_task(task_id='clean')
    def remove_netcdf(**context):
        ti = context['ti']
        file = ti.xcom_pull(task_ids='extract')
        Path(file).unlink(missing_ok=False)

    TL = upload_dataset()
    clean = remove_netcdf()

    E >> TL >> clean
