#* Variables
SHELL:=/usr/bin/env bash
ARGS:=
CONSOLE:=bash
TIMEOUT:=180

include .env

# -- Docker --
.PHONY: containers-build
containers-build:
	containers-sugar --group base build

.PHONY: containers-start
containers-start:
	containers-sugar --group airflow start

.PHONY: containers-down
containers-down:
	containers-sugar --group airflow down

# .PHONY: containers-wait
# containers-wait:
    # TODO

.PHONY: env
env:
	envsubst < env.tpl > .env

.PHONY: linter
linter:
	pre-commit run --all-files --verbose
