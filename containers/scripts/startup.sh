#!/usr/bin/env bash

set -e

# initdb
: "=========== init-db ==========="
. /opt/scripts/init-db.sh

# create admin user
: "=========== init-db ==========="
. /opt/scripts/create-admin.sh

# start airflow
: "========= airflow webserver ========="
airflow webserver &
sleep 10

# start scheduler
: "========= airflow scheduler ========="
airflow scheduler &
sleep 10

# just to keep the prompt blocked
mkdir -p /tmp/empty
cd /tmp/empty

: "========= DONE ========="
python -m http.server
