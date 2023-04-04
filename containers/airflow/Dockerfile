FROM condaforge/mambaforge as base

USER root
ARG UID=1000
ARG GID=1000

ENV ENV_NAME=alertflow

SHELL ["/bin/bash", "-c"]
# Use bash in Dockerfile RUN commands and make sure bashrc is sourced when
# executing commands with /bin/bash -c

RUN apt-get -qq update --yes \
  && apt-get -qq install --yes --no-install-recommends \
  build-essential \
  git \
  make \
  postgresql-client \
  vim \
  ca-certificates \
  wget \
  locales \
  curl \
  cron \
  sudo \
  pip \
  libpq-dev \
  python3-dev \
  libldap2-dev \
  libsasl2-dev \
  ldap-utils \
  tox \
  lcov \
  valgrind \
  unixodbc-dev \
  && rm -rf /var/lib/apt/lists/* \
  && addgroup --gid ${GID} airflow \
  && useradd --uid ${UID} --gid ${GID} -ms /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && export ENV_NAME="$ENV_NAME" \
  && mkdir -p \
    /opt/conda \
    /opt/services/ \
  && chmod -R a+rwx /opt/conda \
  && chown -R airflow:airflow /opt/services /opt/conda

#Set locale
RUN sed -i -e "s/# pt_BR.*/pt_BR.UTF-8 UTF-8/" /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=pt_BR.UTF-8

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH /opt/conda/envs/$ENV_NAME/bin:$PATH

USER airflow

WORKDIR /opt/services/

ENV AIRFLOW_HOME=/opt/services/alertflow
ENV PATH /opt/conda/envs/$ENV_NAME/bin:$PATH
ENV PYTHONPATH='/opt/services/alertflow'

# Change shell to bash
SHELL ["/bin/bash", "-c"]

RUN sudo mkdir -p /opt/scripts /sources ${AIRFLOW_HOME} \
  && echo ". /entrypoint.sh" >> ~/.bashrc \
  && sudo chown -R airflow:airflow /opt/scripts \
  && sudo chown -R airflow:airflow /sources \
  && sudo chown -R airflow:airflow ${AIRFLOW_HOME}
  

COPY --chown=airflow:airflow poetry.lock pyproject.toml README.md /opt/services/
COPY --chown=airflow:airflow conda/env-base.yaml /tmp/conda/env-base.yaml
COPY --chown=airflow:airflow containers/scripts/* /opt/scripts/
COPY --chown=airflow:airflow containers/scripts/entrypoint.sh /entrypoint.sh
COPY --chown=airflow:airflow containers/airflow/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
COPY --chown=airflow:airflow containers/airflow/__init__.py ${AIRFLOW_HOME}/__init__.py

# ref: https://stackoverflow.com/questions/44331836/apt-get-install-tzdata-noninteractive
RUN sudo ln -fs /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime \
  && sudo chmod -R a+rwx /opt/scripts

# Use environment to create the env-satellite
RUN mamba env create -n $ENV_NAME --file /tmp/conda/env-base.yaml \
  && conda clean --all \
  && find /opt/conda/ -type f,l -name '*.pyc' -delete \
  && find /opt/conda/ -type f,l -name '*.js.map' -delete \
  && rm -rf /opt/conda/pkgs /tmp/*

SHELL ["/bin/bash", "-c"]

RUN source /opt/scripts/poetry.sh

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
CMD ["/bin/bash", "/opt/scripts/startup.sh"]
