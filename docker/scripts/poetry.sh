#!/usr/bin/env bash

set -ex

poetry config virtualenvs.create false
poetry install --without "dev,pre-commit"
