FROM apache/airflow:slim-3.2.1-python3.14

LABEL maintainer="Luã Bida Vacaro <luabidaa@gmail.com>"
LABEL org.opencontainers.image.title="AlertFlow"
LABEL org.opencontainers.image.authors="InfoDengue Team"
LABEL org.opencontainers.image.source="https://github.com/AlertaDengue/AlertFlow"
LABEL org.opencontainers.image.version="latest"
LABEL org.opencontainers.image.description="AlertFlow containers system for AlertaDengue"

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
  postgresql-client \
  wget \
  gettext \
  build-essential \
  libffi-dev \
  libreadline-dev \
  sqlite3 \
  libsqlite3-dev \
  zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

RUN cd /tmp \
  && wget https://www.python.org/ftp/python/3.12.3/Python-3.12.3.tgz \
  && tar -xf Python-3.12.3.tgz \
  && cd Python-3.12.3 \
  && ./configure --enable-optimizations --prefix=/opt/pysus \
  && make -j$(nproc) \
  && make altinstall \
  && rm -rf /tmp/Python-3.12.3*

RUN /opt/pysus/bin/python3.12 -m ensurepip --default-pip \
  && /opt/pysus/bin/pip3.12 install --upgrade pip setuptools wheel \
  && /opt/pysus/bin/pip3.12 install pendulum apache-airflow-task-sdk \
  && /opt/pysus/bin/pip3.12 install "pysus==2.0.4"

RUN addgroup --gid ${HOST_GID} airflow \
  && usermod -u ${HOST_UID} -g ${HOST_GID} -d /home/airflow -s /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && chown -R ${HOST_UID}:${HOST_GID} ${AIRFLOW_HOME}/ /opt/airflow/ /opt/pysus/

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH "$PATH:/usr/bin/dirname"

COPY --chown=airflow scripts/entrypoint.sh /entrypoint.sh
COPY --chown=airflow pyproject.toml README.md ${AIRFLOW_HOME}
RUN chmod +x /entrypoint.sh

USER airflow

RUN curl -sSL https://install.python-poetry.org | python3

WORKDIR ${AIRFLOW_HOME}

RUN poetry config virtualenvs.create false \
  && poetry install --no-root --only main

ENTRYPOINT [ "/entrypoint.sh" ]
