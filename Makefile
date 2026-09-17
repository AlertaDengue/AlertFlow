#* Variables
SERVICES:=
SERVICE:=
CMD:=
ARGS:=
TIMEOUT:=90
COMPOSE_FILE ?= docker-compose.dev.yaml

include .env

# -- Project --
.PHONY: env
env:
	envsubst < env.tpl > .env

.PHONY: linter
linter:
	pre-commit run --all-files --verbose

# -- Docker --
build:
	set -e
	docker compose -f ${COMPOSE_FILE} build ${SERVICES}

start:
	set -ex
	docker compose -f ${COMPOSE_FILE} up --remove-orphans -d ${SERVICES}

stop:
	set -ex
	docker compose -f ${COMPOSE_FILE} stop ${ARGS} ${SERVICES}

rm:
	set -ex
	docker compose -f ${COMPOSE_FILE} rm ${ARGS} ${SERVICES}

restart: containers-stop containers-start

down:
	docker compose -f ${COMPOSE_FILE} down ${ARGS}

logs:
	docker compose -f ${COMPOSE_FILE} logs ${ARGS} ${SERVICES}

wait:
	timeout ${TIMEOUT} scripts/healthcheck.sh ${SERVICE}

wait-all:
	$(MAKE) wait SERVICE="scheduler"
	$(MAKE) wait SERVICE="triggerer"
	$(MAKE) wait SERVICE="webserver"
	$(MAKE) wait SERVICE="worker"
