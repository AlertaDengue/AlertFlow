#!/usr/bin/env bash

set -e

# start airflow
airflow webserver
echo "[INFO] Airflow webserver is running at port ${AIRFLOW_PORT}"
