#!/usr/bin/env bash

set -e

# Set the UID and GID to the current user
export HOST_UID=$(id -u)
export HOST_GID=$(id -g)

chown -R ${HOST_UID}:${HOST_GID} $(pwd)

# prepare the conda environment
is_conda_in_path=$(echo $PATH|grep -m 1 --count /opt/conda/)

if [ $is_conda_in_path == 0 ]; then
  export PATH="/opt/conda/condabin:/opt/conda/bin:$PATH"
  echo "[INFO] included conda to the PATH"
fi

echo "[INFO] activate alertflow"
source activate alertflow

# Give permissions to alertflow user to access working directory sources
mkdir -p ${AIRFLOW_HOME}/logs ${AIRFLOW_HOME}/dags ${AIRFLOW_HOME}/plugins
chown -R "${HOST_UID}:${HOST_GID}" ${AIRFLOW_HOME}/{logs,dags,plugins}

airflow version
airflow db init

sleep 3

# Creates user if not exists
users_list=`airflow users list`
no_users='No data found'
if [ "$users_list" = "$no_users" ]; then
  airflow users create \
    --username ${_AIRFLOW_WWW_USER_USERNAME} \
    --password ${_AIRFLOW_WWW_USER_PASSWORD} \
    --email ${_AIRFLOW_WWW_USER_EMAIL} \
    --firstname ${_AIRFLOW_WWW_USER_FIRST_NAME} \
    --lastname ${_AIRFLOW_WWW_USER_LAST_NAME} \
    --role Admin
fi

if [ $# -ne 0 ]
  then
    echo "Running: ${@}"
    $(${@})
fi
