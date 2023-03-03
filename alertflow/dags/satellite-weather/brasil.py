import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path, PosixPath

import asyncpg
import pandas as pd
import pendulum
import satellite_downloader as sat_d
import satellite_weather as sat_w
from airflow.decorators import dag, task
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from satellite_weather._brazil.extract_latlons import MUNICIPIOS

env = os.getenv
email_main = env('EMAIL_MAIN')
DATA_DIR = '/tmp/copernicus'
DEFAULT_ARGS = {
    'owner': 'AlertaDengue',
    'depends_on_past': False,
    'email': [email_main],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
    'start_date': pendulum.datetime(2000, 1, 1),
    'catchup': True,
}

PG_URI_MAIN = (
    'postgresql://'
    f"{env('PSQL_USER_MAIN')}"
    f":{env('PSQL_PASSWORD_MAIN')}"
    f"@{env('PSQL_HOST_MAIN')}"
    f":{env('PSQL_PORT_MAIN')}"
    f"/{env('PSQL_DB_MAIN')}"
)


@dag(
    dag_id='COPERNICUS_BRASIL',
    description='ETL of weather data for Brazil',
    tags=['Brasil', 'Copernicus'],
    schedule_interval='@daily',
    default_args=DEFAULT_ARGS,
)
def brasil():
    async def _load_and_insert(file):
        dataset = sat_w.load_dataset(file)
        for mun in MUNICIPIOS:
            df = dataset.copebr.to_dataframe(mun['geocodigo'], raw=True)
            insert = await _to_sql(df, 'copernicus_brasil')
            return insert

    @task(task_id='loading')
    def loading(**kwargs):
        ti = kwargs['ti']
        netcdf_file = ti.xcom_pull(task_ids='extract')
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(_load_and_insert(netcdf_file))
        return res

    start = initial_task()
    E = download_netcdf()
    L = loading()
    clean = delete_netcdf()

    start >> check_date
    check_date >> stop >> done
    check_date >> proceed >> E >> L >> clean >> done


@dag(
    dag_id='COPERNICUS_FOZ_DO_IGACU',
    description='ETL of weather data for Foz do Iguaçu - BR',
    tags=['Brasil', 'Copernicus'],
    schedule_interval='@weekly',
    default_args=DEFAULT_ARGS,
)
def foz_do_iguacu():
    async def _load_and_insert(file):
        dataset = sat_w.load_dataset(file)
        df = dataset.copebr.to_dataframe(4108304, raw=True)
        insert = await _to_sql(df, 'copernicus_foz_do_iguacu')
        return insert

    @task(task_id='loading')
    def loading(**kwargs):
        ti = kwargs['ti']
        netcdf_file = ti.xcom_pull(task_ids='extract')
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(_load_and_insert(netcdf_file))
        return res

    start = initial_task()
    E = download_netcdf(data_days_interval=7)
    L = loading()
    clean = delete_netcdf()

    start >> check_date
    check_date >> stop >> done
    check_date >> proceed >> E >> L >> clean >> done


@task(task_id='start')
def initial_task():
    exec_date = '{{ ds }}'
    Path(DATA_DIR).mkdir(exist_ok=True)
    return datetime.date(exec_date)


def _is_date_available(date: datetime.date) -> bool:
    max_data_delay = datetime.date(datetime.now() - timedelta(days=7))
    return 'yes' if date < max_data_delay else 'no'


check_date = BranchPythonOperator(
    task_id='is_date_available',
    python_callable=_is_date_available,
    op_kwargs={'date': '{{ ds }}'},
)

proceed = EmptyOperator(task_id='yes')

stop = EmptyOperator(task_id='no')


@task(task_id='extract')
def download_netcdf(
    data_days_interval: int = None, data_dir=DATA_DIR, **kwargs
) -> PosixPath:
    ti = kwargs['ti']
    ini_date = ti.xcom_pull(task_ids='start')

    if not data_days_interval:
        end_date = None
    else:
        end_date = datetime.date(ini_date - timedelta(days=data_days_interval))

    try:
        netcdf_file = sat_d.download_br_netcdf(
            date=ini_date, end_date=end_date, data_dir=data_dir
        )
        return Path(data_dir) / netcdf_file
    except Exception as e:
        raise e


async def _to_sql(dataframe: pd.DataFrame, tablename: str, timeout=None):
    connection = await asyncpg.connect(dsn=PG_URI_MAIN)
    insert = await connection.copy_records_to_table(
        tablename,
        records=dataframe.values.tolist(),
        columns=dataframe.columns,
        schema_name='weather',
        timeout=timeout,
    )
    await connection.close()
    return insert


@task(task_id='clean')
def delete_netcdf(**kwargs):
    ti = kwargs['ti']
    netcdf_file = ti.xcom_pull(task_ids='extract')
    Path(netcdf_file).unlink(missing_ok=False)


done = EmptyOperator(
    task_id='done',
    trigger_rule='one_success',
)
