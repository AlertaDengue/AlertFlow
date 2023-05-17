import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from dotenv import dotenv_values, set_key


def set_airflow_variables():
    """
    Set Airflow variables from environment and write them to the .env file.
    """
    # Set Airflow variables from environment variables
    PSQL_USER = os.environ.get('AIRFLOW_PSQL_USER_MAIN')
    PSQL_PASSWORD = os.environ.get('AIRFLOW_PSQL_PASSWORD_MAIN')
    PSQL_HOST = os.environ.get('AIRFLOW_PSQL_HOST_MAIN')
    PSQL_PORT = os.environ.get('AIRFLOW_PSQL_PORT_MAIN')
    PSQL_DB = os.environ.get('AIRFLOW_PSQL_DB_MAIN')

    Variable.set('PSQL_USER', PSQL_USER)
    Variable.set('PSQL_PASSWORD', PSQL_PASSWORD)
    Variable.set('PSQL_HOST', PSQL_HOST)
    Variable.set('PSQL_PORT', PSQL_PORT)
    Variable.set('PSQL_DB', PSQL_DB)

    # Write variables to .env file
    dotenv_path = '/opt/airflow/episcanner-downloader/.env'
    env_vars = dotenv_values(dotenv_path)
    env_vars['PSQL_USER'] = PSQL_USER
    env_vars['PSQL_PASSWORD'] = PSQL_PASSWORD
    env_vars['PSQL_HOST'] = PSQL_HOST
    env_vars['PSQL_PORT'] = PSQL_PORT
    env_vars['PSQL_DB'] = PSQL_DB
    for key, value in env_vars.items():
        set_key(dotenv_path, key, value)


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 5, 21),
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'EPISCANNER_DOWNLOADER',
    default_args=default_args,
    schedule_interval='0 3 * * 0',  # Every Sunday at 3 AM
    catchup=False,
) as dag:

    # clone the repository from GitHub
    clone_repository = BashOperator(
        task_id='clone_repository',
        bash_command='git clone --branch main --single-branch --depth 1 '
        'https://github.com/AlertaDengue/episcanner-downloader.git '
        '/opt/airflow/episcanner-downloader',
        dag=dag,
    )

    # Set variables for Episcanner-PostgreSQL connection
    set_connection_variables = PythonOperator(
        task_id='set_connection_variables',
        python_callable=set_airflow_variables,
        dag=dag,
    )

    # Install the Episcanner package using Poetry
    install_episcanner = BashOperator(
        task_id='install_episcanner',
        bash_command='source /home/airflow/mambaforge/bin/activate episcanner-downloader && '  # NOQA E501
        'cd /opt/airflow/episcanner-downloader && '
        'poetry install',
        dag=dag,
    )

    # Download all data to the specified directory
    episcanner_downloader = BashOperator(
        task_id='episcanner_downloader',
        bash_command='source /home/airflow/mambaforge/bin/activate episcanner-downloader && '  # NOQA E501
        'cd /opt/airflow/episcanner-downloader &&'
        'python epi_scanner/downloader/export_data.py '
        '-s all -d dengue chikungunya -o /opt/airflow/episcanner_data',
        dag=dag,
    )

    # Remove the episcanner-downloader repository
    remove_repository = BashOperator(
        task_id='remove_repository',
        bash_command='rm -rf /opt/airflow/episcanner-downloader',
        dag=dag,
    )

    (
        clone_repository
        >> set_connection_variables
        >> install_episcanner
        >> episcanner_downloader
        >> remove_repository
    )
