import os
import pendulum

from dateutil import parser
from pathlib import Path, PosixPath
from sqlalchemy import create_engine
from datetime import timedelta

from satellite import weather as sat_w
from satellite import downloader as sat_d
from satellite.weather._brazil.extract_latlons import MUNICIPIOS

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
    catchup=True,
):

    def download_netcdf(ini_date: str) -> PosixPath:
        """ 
        Downloads the file for current task execution 
        date - 9 days for safety reasons. Returns the
        local NetCDF4 file to be inserted into postgres. 
        """
        start_date = parser.parse(str(ini_date)).date()
        max_update_delay = start_date - timedelta(days=9)

        try:
            netcdf_file = sat_d.download_br_netcdf(date=str(max_update_delay),data_dir=DATA_DIR)
            filepath = Path(DATA_DIR) / netcdf_file
            return str(filepath.absolute())
        except Exception as e:
            raise e

    # https://airflow.apache.org/docs/apache-airflow/stable/templates-ref.html#variables
    E = PythonOperator(
        task_id='extract',
        python_callable=download_netcdf,
        op_kwargs={'ini_date': '{{ ds }}'},
    )

    @python_task(task_id='loading')
    def upload_dataset(**context) -> PosixPath:
        """ 
        Reads the NetCDF file and generate the dataframe for all 
        geocodes from IBGE using XArray and insert every geocode
        into postgres database.
        """
        ti = context['ti']
        file = ti.xcom_pull(task_ids='extract')
        ds = sat_w.load_dataset(file)
        geocodes = [mun['geocodigo'] for mun in MUNICIPIOS]
        
        for geocode in geocodes:
            df = ds.copebr.to_dataframe(geocodes=geocode, raw=False)
            with create_engine(PG_URI_MAIN).connect() as conn:
                df.to_sql(
                    name=TABLE_NAME,
                    schema=SCHEMA,
                    con=conn,
                    if_exists='append'
                )

    @python_task(task_id='clean')
    def remove_netcdf(**context):
        """ Remove the file downloaded by extract task """
        ti = context['ti']
        file = ti.xcom_pull(task_ids='extract')
        Path(file).unlink(missing_ok=False)

    # Creating the tasks
    TL = upload_dataset()
    clean = remove_netcdf()

    # Task flow
    E >> TL >> clean
