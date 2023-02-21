# Building Development Environment

## Install mamba
In order to create the development environment, it will be needed mamba or conda related environment manager. Please follow [mamba installation instructions](https://mamba.readthedocs.io/en/latest/installation.html) to
install mamba in your local machine, you can also use conda, mambaforge, micromamba and
others.

## Create & Activate the Virtual Environment
``` bash
$ mamba create -c conda-forge --file conda/env.yaml
$ conda activate alertflow
```

## Install dev dependencies with Poetry
``` bash
$ poetry install 
```

## Configure environment variables
Airflow containers depend on some environment variables, these variables can be
found in the `env.tpl` file. The variables with double brackets `{{}}` can be replaced with the output of their bash commands. After configuring the variables, run:
``` bash
$ make env
```

# Starting containers
The [compose](docker/compose.yaml) file will be responsible for building and running all containers, use `make` commands to run & stop the containers
``` bash
$ make containers-start
$ make containers-stop
```

# Committing

## Commits format
AlertFlow uses [Semantic Release](https://github.com/semantic-release/semantic-release) commit format, please read SM documentation before committing.

## Linting
Format code using `make linter`. Note that linting is a required step to pass on CI.
