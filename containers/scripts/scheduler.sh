#!/usr/bin/env bash

set -e

# start scheduler
airflow scheduler
echo "[INFO] Airflow scheduler is up"
