#!/usr/bin/env bash

set -e

: "[INFO] Running poetry install"
poetry config virtualenvs.create false
poetry install --only main
