import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.sdk import Variable

with DAG(
    dag_id="PYSUS",
    schedule=None,
    start_date=pendulum.datetime(2026, 1, 1),
    catchup=False,
) as dag:
    ACCESS = Variable.get("pysus_s3_access_key", deserialize_json=True)
    SECRET = Variable.get("pysus_s3_secret_key", deserialize_json=True)
    DADOSGOV = Variable.get("pysus_dadosgov_token", deserialize_json=True)

    @task.external_python(
        task_id="pysus_update_s3_files",
        python="/opt/pysus/bin/python3.12",
    )
    def callable_external_python(access_key: str, secret_key: str):
        import sys
        import time

        print(access_key)
        print(secret_key)
        print(f"Running task via {sys.executable}")
        print("Sleeping")
        for _ in range(4):
            print("Please wait...", flush=True)
            time.sleep(1)
        print("Finished")

    external_python_task = callable_external_python(
        ACCESS["PYSUS_S3_ACCESS_KEY"],
        SECRET["PYSUS_S3_SECRET_KEY"],
    )
