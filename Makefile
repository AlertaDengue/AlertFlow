#* Variables
SERVICES:=
SERVICE:=
CMD:=
ARGS:=
TIMEOUT:=90

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
	docker compose build ${SERVICES}

start:
	set -ex
	docker compose up --remove-orphans -d ${SERVICES}

stop:
	set -ex
	docker compose stop ${ARGS} ${SERVICES}

rm:
	set -ex
	docker compose rm ${ARGS} ${SERVICES}

restart: containers-stop containers-start

down:
	docker compose down ${ARGS}

logs:
	docker compose logs ${ARGS} ${SERVICES}

wait:
	timeout ${TIMEOUT} scripts/healthcheck.sh ${SERVICE}

wait-all:
	$(MAKE) wait SERVICE="scheduler"
	$(MAKE) wait SERVICE="triggerer"
	$(MAKE) wait SERVICE="webserver"
	$(MAKE) wait SERVICE="worker"
