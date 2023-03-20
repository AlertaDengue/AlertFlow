#!/usr/bin/env bash

set -e

chown -R airflow:airflow "${AIRFLOW_HOME}"/{dags,logs,plugins}

# initdb
: "[INFO] running init-db.sh"
. /opt/scripts/init-db.sh &&
sleep 5

# create admin user
: "[INFO] running create-admin.sh"
. /opt/scripts/create-admin.sh &&
sleep 5

# start airflow
: "[INFO] running airflow webserver"
airflow webserver &&
sleep 5

# start scheduler
: "[INFO] running airflow scheduler"
airflow scheduler &&
sleep 5

# just to keep the prompt blocked
mkdir -p /tmp/empty
cd /tmp/empty

: "[INFO] Done"
# python -m http.server
