# Core
VOLUMES_HOST_DIR="{{ pwd }}/volumes"
AIRFLOW_IMAGE_NAME=apache/airflow:2.5.1
HOST_UID="{{ id -u }}"
HOST_GID="{{ id -g }}"

# Web
AIRFLOW_PORT=
_AIRFLOW_WWW_USER_USERNAME=
_AIRFLOW_WWW_USER_PASSWORD=

# Email
EMAIL_MAIN=

# External Postgres Connection
# https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html
PSQL_USER_MAIN=
PSQL_PASSWORD_MAIN=
PSQL_HOST_MAIN=
PSQL_PORT_MAIN=
PSQL_DB_MAIN=

# Satellite Weather (format: CDSAPI_KEY="UID:KEY")
# https://cds.climate.copernicus.eu/user/{MY_USER}
CDSAPI_KEY=

# Extras
AIRFLOW__CORE__FERNET_KEY=''
