FROM condaforge/mambaforge as base

ENV ENV_NAME=alertadengue

USER root

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
  && rm -rf /var/lib/apt/lists/*

#Set locale
RUN sed -i -e "s/# pt_BR.*/pt_BR.UTF-8 UTF-8/" /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=pt_BR.UTF-8 

# Create airflow user
RUN addgroup --gid 1000 airflow \
  && useradd --uid 1000 --gid 1000 -ms /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && export ENV_NAME="$ENV_NAME" \
  && mkdir -p \
    /opt/conda \
    /opt/alertflow/ \
  && chmod -R a+rwx /opt/conda /opt/alertflow /tmp \
  && chown -R airflow:airflow /opt/alertflow/ /tmp \
  && echo 'source activate "$ENV_NAME"' >  /home/airflow/.bashrc \
  && printenv | sed 's/^\(.*\)$/export \1/g' >> /preload.sh

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH /opt/conda/envs/$ENV_NAME/bin:$PATH

USER airflow

# Change shell to bash
SHELL ["/bin/bash", "-c"]
WORKDIR /opt/alertflow

# Use environment to create the env-satellite
COPY --chown=airflow:airflow conda/env.yaml /tmp/conda/env.yaml
RUN mamba env create -n $ENV_NAME -f /tmp/conda/env.yaml \
  && conda clean --all \
  && find /opt/conda/ -type f,l -name '*.a' -delete \
  && find /opt/conda/ -type f,l -name '*.pyc' -delete \
  && find /opt/conda/ -type f,l -name '*.js.map' -delete

COPY --chown=airflow:airflow docker/airflow-extras.in /tmp/airflow-extras.in
RUN pip install --root-user-action ignore -r /tmp/airflow-extras.in

COPY --chown=airflow:airflow poetry.lock pyproject.toml airflow.cfg /opt/alertflow/
COPY --chown=airflow:airflow docker/scripts/poetry.sh /tmp/poetry-install.sh
RUN bash /tmp/poetry-install.sh

COPY --chown=airflow:airflow docker/scripts/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["bash", "/entrypoint.sh"]
