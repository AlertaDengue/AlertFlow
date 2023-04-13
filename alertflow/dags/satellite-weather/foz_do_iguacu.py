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
    dag_id='COPERNICUS_FOZ',
    description='ETL of weather data for Foz do Iguaçu - BR',
    tags=['Brasil', 'Copernicus', 'Foz do Iguaçu'],
    schedule='@weekly',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2000, 1, 9),
    catchup=False,  # TODO CHANGE TO TRUE
    max_active_runs=15,
):

    DATE = '{{ ds }}'

    @task.external_python(
        task_id='weekly_fetch', python='/opt/py310/bin/python3.10'
    )
    def extract_transform_load(
        date: str, data_dir: str, api_key: str, psql_uri: str
    ) -> None:
        from pathlib import Path
        from dateutil import parser
        from itertools import chain
        from datetime import timedelta

        from satellite import downloader as sat_d
        from satellite import weather as sat_w
        from sqlalchemy import create_engine

        try:
            with create_engine(psql_uri).connect() as conn:
                cur = conn.execute(
                    'SELECT DISTINCT(datetime::DATE) '
                    'FROM weather.copernicus_foz_do_iguacu'
                )
                dates = list(chain(*cur.all()))
        except Exception as e:
            if 'UndefinedTable' in str(e):
                print('First insertion')
                dates = []
            else:
                raise e

        exec_date = parser.parse(str(date)).date()
        max_update_delay = exec_date - timedelta(days=9)
        start_date = max_update_delay - timedelta(days=7)

        format_date = lambda dt: dt.strftime('%F')
        if str(format_date(start_date)) in list(map(format_date, dates)):
            print(f'[INFO] {date} has been fetched already.')
            return None

        netcdf_file = sat_d.download_br_netcdf(
            date=str(start_date),
            date_end=str(max_update_delay),
            data_dir=data_dir,
            user_key=api_key,
        )
        filepath = Path(data_dir) / netcdf_file

        ds = sat_w.load_dataset(filepath)

        df = ds.copebr.to_dataframe(4108304, raw=True)

        with create_engine(psql_uri).connect() as conn:
            df.to_sql(
                name='copernicus_foz_do_iguacu',
                schema='weather',
                con=conn,
                if_exists='append',
            )
        print(f'{filepath} inserted into weather.copernicus_foz_do_iguacu')
        
        Path(filepath).unlink(missing_ok=True)

    ETL = extract_transform_load(DATE, DATA_DIR, CDSAPI_KEY, PG_URI_MAIN)

    ETL
