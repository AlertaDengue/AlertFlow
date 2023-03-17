#!/usr/bin/env bash

set -e

# prepare the conda environment
is_conda_in_path=$(echo $PATH|grep -m 1 --count /opt/conda/)

if [ $is_conda_in_path == 0 ]; then
  export PATH="/opt/conda/condabin:/opt/conda/bin:$PATH"
  : "[II] included conda to the PATH"
fi

: "[II] activate alertflow"
source activate alertflow

if [ $# -ne 0 ]
  then
    : "Running: ${@}"
    $(${@})
fi
