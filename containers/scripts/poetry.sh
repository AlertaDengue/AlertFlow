#!/usr/bin/env bash

set -e

echo "[INFO] Running poetry install"
poetry config virtualenvs.create false
poetry install --only main
