# Core
AIRFLOW_PROJ_DIR="{{ pwd }}/alertflow"
AIRFLOW_IMAGE_NAME=apache/airflow:2.5.1
AIRFLOW_UID="{{ id -u }}"

# Web
_AIRFLOW_WWW_USER_USERNAME=
_AIRFLOW_WWW_USER_PASSWORD=

# External Postgres Connection
# https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html
PSQL_USER=
PSQL_PASSWORD=
PSQL_HOST=
PSQL_PORT=
PSQL_DB=
AIRFLOW_CONN_POSTGRES_DEFAULT='postgresql://${PSQL_USER}:${PSQL_PASSWORD}@${PSQL_HOST}:${PSQL_PORT}/${PSQL_DB}'

# Extras [pip]
_PIP_ADDITIONAL_REQUIREMENTS=''
