# Core
AIRFLOW_PROJ_DIR="{{ pwd }}/alertflow"
AIRFLOW_IMAGE_NAME=apache/airflow:2.5.1
AIRFLOW_UID="{{ id -u }}"
AIRFLOW_GID="{{ id -g }}"

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
# Do not change
AIRFLOW_CONN_POSTGRES_MAIN='postgresql://${PSQL_USER}:${PSQL_PASSWORD}@${PSQL_HOST}:${PSQL_PORT}/${PSQL_DB}'

# Extras
AIRFLOW__CORE__FERNET_KEY=''
