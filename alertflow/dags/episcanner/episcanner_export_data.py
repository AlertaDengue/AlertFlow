from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# Define default arguments for the DAG
default_args = {
    'owner': 'AlertaDengue',
    'depends_on_past': False,
    'start_date': datetime(2023, 5, 3),
    'retries': 1,
    'retry_delay': timedelta(minutes=5)
}

# Define the DAG, default arguments, and a schedule interval
with DAG('EPISCANNER_EXPORT_DATA', default_args=default_args, schedule_interval='0 3 * * 0') as dag:

    # install conda
    t1 = BashOperator(
        task_id='install_conda',
        bash_command='wget -O /tmp/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && bash /tmp/miniconda.sh -b -p $HOME/miniconda && export PATH="$HOME/miniconda/bin:$PATH" && conda init bash',
        dag=dag
    )

    # create the episcanner environment
    t2 = BashOperator(
        task_id='create_environment',
        bash_command='source $HOME/.bashrc && conda env create -f https://github.com/AlertaDengue/epi-scanner/raw/main/conda/env-base.yaml -n episcanner',
        dag=dag
    )

    # clone the repository from GitHub
    t3 = BashOperator(
        task_id='clone_repository',
        bash_command='git clone https://github.com/AlertaDengue/epi-scanner.git',
        dag=dag
    )

    # install dependencies and run the export script
    t4 = BashOperator(
        task_id='install_dependencies',
        bash_command='source $HOME/.bashrc && cd epi-scanner && poetry install ',
        dag=dag
    )

    # activate the episcanner environment and run the export data script
    t5 = BashOperator(
        task_id='export_data',
        bash_command='source $HOME/.bashrc && conda activate episcanner && python epi_scanner/management/export_data.py -s all -d dengue chikungunya -o data',
        dag=dag,
    )

    t1 >> t2 >> t3 >> t4 >> t5
