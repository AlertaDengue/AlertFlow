#!/usr/bin/env bash

set -e

if [ $# -eq 0 ]; then
  exit 0
fi

# prepare the conda environment
is_conda_in_path=$(echo "$PATH"|grep -m 1 --count /opt/conda/)

if [ "$is_conda_in_path" == 0 ]; then
  export PATH="/opt/conda/condabin:/opt/conda/bin:$PATH"
  echo "[INFO] included conda to the PATH"
fi

echo "[INFO] activate alertflow"
# shellcheck disable=SC1091
. /opt/conda/etc/profile.d/conda.sh &&
conda activate alertflow

# shellcheck disable=SC2145
echo "Running: ${@}"
# shellcheck disable=SC2091
$("${@}")
