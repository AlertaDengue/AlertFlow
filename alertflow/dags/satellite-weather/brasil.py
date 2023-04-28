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
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.decorators import task

env = os.getenv
email_main = env('EMAIL_MAIN')

DEFAULT_ARGS = {
    'owner': 'AlertaDengue',
    'depends_on_past': False,
    # 'email': [email_main],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=2),
}


with DAG(
    dag_id='COPERNICUS_BRASIL',
    description='ETL of weather data for Brazil',
    tags=['Brasil', 'Copernicus'],
    schedule='@monthly',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2015, 1, 16),
    catchup=True,
    max_active_runs=4,
):
    from airflow.models import Variable

    DATE = '{{ ds }}'   # DAG execution date
    DATA_DIR = '/tmp/copernicus'
    KEY = Variable.get('cdsapi_key', deserialize_json=True)
    URI = Variable.get('psql_main_uri', deserialize_json=True)

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
        import calendar
        from datetime import timedelta, datetime
        from pathlib import Path

        from dateutil import parser
        from satellite import downloader as sat_d
        from satellite import weather as sat_w
        from satellite.weather._brazil.extract_latlons import MUNICIPIOS
        from sqlalchemy import create_engine

        start_date = parser.parse(str(date))
        # max_update_delay = start_date - timedelta(days=8)

        if start_date.month == 1:
            ini_date = datetime(start_date.year - 1, 12, 1).date()
        else:
            ini_date = datetime(start_date.year, start_date.month - 1, 1).date()

        end_date = datetime(
            ini_date.year,
            ini_date.month,
            calendar.monthrange(ini_date.year, ini_date.month)[1],
        ).date()


        # Downloads daily dataset
        netcdf_file = sat_d.download_br_netcdf(
            date=str(ini_date),
            date_end=str(end_date), 
            data_dir=data_dir, 
            user_key=api_key['CDSAPI_KEY']
        )

        print(f'Handling {netcdf_file}')

        # Reads the NetCDF4 file using Xarray
        ds = sat_w.load_dataset(netcdf_file)
        geocodes = [mun['geocodigo'] for mun in MUNICIPIOS]

        def geocode_in_db(geocode: int) -> bool:
            # Checks if date has been already inserted into DB
            try:
                with create_engine(psql_uri['PSQL_MAIN_URI']).connect() as conn:
                    cur = conn.execute(
                        'SELECT EXISTS ('
                        ' SELECT FROM weather.copernicus_brasil'
                        f" WHERE date = '{ini_date}' AND geocodigo = {geocode}"
                        ')'
                    )
                    return cur.fetchone()[0]
            except Exception as e:
                if 'UndefinedTable' in str(e):
                    # For dev purposes, in case table was not found
                    print('First insertion')
                    return False
                else:
                    raise e

        for geocode in geocodes:
            print(f'Handling {geocode}', flush=True)

            if geocode_in_db(geocode):
                print(f'{geocode} already in DB')
                continue

            try:
                ds.copebr.to_sql(
                    tablename='copernicus_brasil',
                    schema='weather',
                    geocodes=geocode,
                    sql_uri=psql_uri['PSQL_MAIN_URI'],
                )
                print(f'{geocode} inserted into DB')
            except Exception as e:
                print(type(e))
                continue

        # Deletes the NetCDF4 file
        Path(netcdf_file).unlink(missing_ok=True)

    # Instantiate the Task
    ETL = extract_transform_load(DATE, DATA_DIR, KEY, URI)

    ETL   # Execute
