#!/usr/bin/env bash

set -e

AH="${AIRFLOW_HOME}"
chown -R airflow:airflow "$AH"/dags "$AH"/logs "$AH"/plugins

echo "[INFO] Running startup scripts"
bash /opt/scripts/init-db.sh && \
bash /opt/scripts/create-admin.sh && \
bash /opt/scripts/scheduler.sh && \
bash /opt/scripts/webserver.sh
echo "[INFO] Airflow initialization done"
