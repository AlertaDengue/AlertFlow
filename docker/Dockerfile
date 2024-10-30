FROM apache/airflow:latest

LABEL maintainer="Luã Bida Vacaro <luabidaa@gmail.com>"
LABEL org.opencontainers.image.title="AlertFlow"
LABEL org.opencontainers.image.authors="InfoDengue Team"
LABEL org.opencontainers.image.source="https://github.com/AlertaDengue/AlertFlow"
LABEL org.opencontainers.image.version="latest"
LABEL org.opencontainers.image.description="Airflow containers system for AlertaDengue"

USER root

ARG HOST_UID
ARG HOST_GID

RUN apt-get update \
  && apt-get install -y \
  curl \
  git \
  vim \
  sed \
  tar \
  lzma \
  libssl-dev \
  libtk8.6 \
  libgdm-dev \
  libdb4o-cil-dev \
  liblzma-dev \
  libpcap-dev \
  libbz2-dev \
  libpq-dev \
  python3-dev \
  python3-venv \
  libsqlite3-dev \
  postgresql-client \
  wget \
  gettext \
  build-essential \
  && rm -rf /var/lib/apt/lists/*


RUN addgroup --gid ${HOST_GID} airflow \
  && usermod -u ${HOST_UID} -g ${HOST_GID} -d /home/airflow -s /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && chown -R ${HOST_UID}:${HOST_GID} ${AIRFLOW_HOME}/ /opt/airflow/

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH "$PATH:/usr/bin/dirname"

COPY --chown=airflow alertflow/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
COPY --chown=airflow docker/scripts/entrypoint.sh /entrypoint.sh
COPY --chown=airflow pyproject.toml ${AIRFLOW_HOME}
RUN chmod +x /entrypoint.sh

USER airflow

RUN curl -sSL https://install.python-poetry.org | python3

WORKDIR ${AIRFLOW_HOME}

RUN poetry config virtualenvs.create false \
  && poetry install --only main

ENTRYPOINT [ "/entrypoint.sh" ]
