#* Variables
SERVICES:=
SERVICE:=
CMD:=
ARGS:=
TIMEOUT:=90

# https://github.com/containers/podman-compose/issues/491#issuecomment-1289944841
CONTAINER_APP=docker compose \
	--env-file=.env \
	--file docker/compose.yaml

include .env

# -- Project --
.PHONY: env
env:
	envsubst < env.tpl > .env

.PHONY: linter
linter:
	pre-commit run --all-files --verbose

# -- Docker --
containers-build:
	set -e
	$(CONTAINER_APP) build ${SERVICES}

containers-start:
	set -ex
	$(CONTAINER_APP) up --remove-orphans -d ${SERVICES}

containers-stop:
	set -ex
	$(CONTAINER_APP) stop ${ARGS} ${SERVICES}

containers-rm:
	set -ex
	$(CONTAINER_APP) rm ${ARGS} ${SERVICES}

containers-restart: containers-stop containers-start

containers-logs:
	$(CONTAINER_APP) logs ${ARGS} ${SERVICES}

containers-wait:
	timeout ${TIMEOUT} docker/scripts/healthcheck.sh ${SERVICE}

containers-wait-all:
	$(MAKE) containers-wait SERVICE="scheduler"
	$(MAKE) containers-wait SERVICE="triggerer"
	$(MAKE) containers-wait SERVICE="webserver"
	$(MAKE) containers-wait SERVICE="worker"
