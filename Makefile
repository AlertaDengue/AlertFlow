#* Variables
SHELL:=/usr/bin/env bash
ARGS:=
CONSOLE:=bash
TIMEOUT:=180

include .env

# -- Docker --
SERVICES=

COMPOSE=docker-compose \
	--env-file .env \
	--project-name AlertFlow \
	--file docker/compose.yaml \


# No need until Dockerfile setup
# .PHONY: containers-build
# containers-build:
# 	$(COMPOSE) build ${SERVICES}

.PHONY: containers-start
containers-start:
	$(COMPOSE) up -d ${SERVICES}

.PHONY: containers-stop
containers-stop:
	$(COMPOSE) down -v --remove-orphans

# .PHONY: containers-wait
# containers-wait:
    # TODO

# --

.PHONY: env
env:
	envsubst < env.tpl > .env

.PHONY: linter
linter:
	pre-commit run --all-files --verbose
