FROM condaforge/mambaforge as base


ENV ENV_NAME=alertflow

USER root

RUN apt-get -qq update --yes \
  && apt-get -qq install --yes --no-install-recommends \
  build-essential git make postgresql-client vim \
  ca-certificates wget locales curl cron sudo \
  && rm -rf /var/lib/apt/lists/*

#Set locale
RUN sed -i -e "s/# pt_BR.*/pt_BR.UTF-8 UTF-8/" /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=pt_BR.UTF-8

# Create deploy user
RUN addgroup --gid 1000 airflow \
  && useradd --uid 1000 --gid 1000 -ms /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && export ENV_NAME="$ENV_NAME" \
  && mkdir -p /opt/conda /opt/services/ \
  && chmod -R a+rwx /opt/conda /opt/services /tmp \
  && chown airflow:airflow /opt/services/ /tmp

# Copy dependencies file
COPY --chown=airflow:airflow conda/env.yaml /tmp/conda/env.yaml
COPY --chown=airflow:airflow docker/scripts/entrypoint.sh /activate.sh

USER airflow

# Use environment to create the env-satellite
RUN mamba env create -n $ENV_NAME \
    --file /tmp/conda/env.yaml \
  && conda clean --all \
  && find /opt/conda/ -type f,l -name '*.a' -delete \
  && find /opt/conda/ -type f,l -name '*.pyc' -delete \
  && find /opt/conda/ -type f,l -name '*.js.map' -delete

RUN poetry config virtualenvs.create false \
    && poetry install --without dev, pre-commit

WORKDIR /opt/alertflow

ENTRYPOINT ["bash", "/activate.sh"]
