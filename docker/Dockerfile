FROM condaforge/mambaforge as base

USER root
ARG HOST_UID=1000
ARG HOST_GID=1000

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
  && rm -rf /var/lib/apt/lists/*

#Set locale
RUN sed -i -e "s/# pt_BR.*/pt_BR.UTF-8 UTF-8/" /etc/locale.gen \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && update-locale LANG=pt_BR.UTF-8

# Create airflow user
RUN addgroup --gid ${HOST_GID} airflow \
  && useradd --uid ${HOST_UID} --gid ${HOST_GID} -ms /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && export ENV_NAME="$ENV_NAME" \
  && mkdir -p \
    /opt/conda \
    /opt/services/alertflow/ \
  && chmod -R a+rwx /opt/conda /opt/services/alertflow /tmp \
  && chown -R ${HOST_GID}:${HOST_GID} /opt/services/alertflow/ \
  && echo 'source activate "$ENV_NAME"' >  /home/airflow/.bashrc

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH /opt/conda/envs/$ENV_NAME/bin:$PATH

USER airflow

# Change shell to bash
SHELL ["/bin/bash", "-c"]

COPY --chown=${HOST_GID}:${HOST_GID} conda/env-base.yaml /tmp/conda/env-base.yaml
COPY --chown=${HOST_GID}:${HOST_GID} poetry.lock pyproject.toml airflow.cfg README.md /opt/services/
COPY --chown=${HOST_GID}:${HOST_GID} docker/scripts/poetry.sh /tmp/poetry-install.sh
COPY --chown=${HOST_GID}:${HOST_GID} docker/scripts/entrypoint.sh /entrypoint.sh
COPY --chown=${HOST_GID}:${HOST_GID} docker/airflow-extras.in /tmp/airflow-extras.in
COPY --chown=${HOST_GID}:${HOST_GID} alertflow/__init__.py /opt/services/alertflow/__init__.py

# Use environment to create the env-satellite
RUN mamba env create -n $ENV_NAME -f /tmp/conda/env-base.yaml \
  && conda clean --all \
  && find /opt/conda/ -type f,l -name '*.a' -delete \
  && find /opt/conda/ -type f,l -name '*.pyc' -delete \
  && find /opt/conda/ -type f,l -name '*.js.map' -delete \
  && rm -rf /home/airflow/.conda/pkgs

RUN pip install --root-user-action ignore -r /tmp/airflow-extras.in

WORKDIR /opt/services/
RUN bash /tmp/poetry-install.sh
ENTRYPOINT ["bash", "/entrypoint.sh"]
