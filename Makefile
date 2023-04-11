#* Variables
SHELL:=/usr/bin/env bash
ARGS:=
CONSOLE:=bash
TIMEOUT:=180

include .env

# -- Docker --
.PHONY: containers-build
containers-build:
	docker compose --env-file .env --file docker/compose.yaml build

.PHONY: containers-start
containers-start:
	docker compose --env-file .env --file docker/compose.yaml up -d

.PHONY: containers-down
containers-down:
	docker compose --env-file .env --file docker/compose.yaml down -v --remove-orphans

# .PHONY: containers-wait
# containers-wait:
    # TODO

.PHONY: env
env:
	envsubst < env.tpl > .env

.PHONY: linter
linter:
	pre-commit run --all-files --verbose
