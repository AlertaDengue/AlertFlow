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
	sugar build ${SERVICES}

start:
	set -ex
	sugar up --remove-orphans -d ${SERVICES}

stop:
	set -ex
	sugar stop ${ARGS} ${SERVICES}

rm:
	set -ex
	sugar rm ${ARGS} ${SERVICES}

restart: containers-stop containers-start

down:
	sugar down ${ARGS}

logs:
	sugar logs ${ARGS} ${SERVICES}

wait:
	timeout ${TIMEOUT} docker/scripts/healthcheck.sh ${SERVICE}

wait-all:
	$(MAKE) wait SERVICE="scheduler"
	$(MAKE) wait SERVICE="triggerer"
	$(MAKE) wait SERVICE="webserver"
	$(MAKE) wait SERVICE="worker"
