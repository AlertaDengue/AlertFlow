# Core
AIRFLOW_PROJ_HOST_DIR="{{ pwd }}/alertflow"
AIRFLOW_VOLUMES_HOST_DIR="{{ pwd }}/volumes"
AIRFLOW_IMAGE_NAME=apache/airflow:2.5.1
HOST_UID="{{ id -u }}"
HOST_GID="{{ id -g }}"

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

# Extras
AIRFLOW__CORE__FERNET_KEY=''
