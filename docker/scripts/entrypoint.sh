#!/usr/bin/env bash

set -e

# prepare the conda environment
is_conda_in_path=$(echo $PATH|grep -m 1 --count /opt/conda/)

if [ $is_conda_in_path == 0 ]; then
  export PATH="/opt/conda/condabin:/opt/conda/bin:$PATH"
  echo "[INFO] included conda to the PATH"
fi

echo "[INFO] activate alertadengue"
source activate alertadengue

airflow version
airflow db init

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
