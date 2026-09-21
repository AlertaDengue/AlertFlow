FROM apache/airflow:slim-3.2.1-python3.14

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
  postgresql-client \
  wget \
  gettext \
  build-essential \
  zlib1g-dev \
  libncurses5-dev \
  libncursesw5-dev \
  libreadline-dev \
  libsqlite3-dev \
  libffi-dev \
  binutils \
  libgdal-dev \
  gdal-bin \
  libproj-dev \
  proj-bin \
  libgeos-dev \
  && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

RUN addgroup --gid ${HOST_GID} airflow \
  && usermod -u ${HOST_UID} -g ${HOST_GID} -d /home/airflow -s /bin/bash airflow \
  && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
  && chmod 0440 /etc/sudoers.d/airflow \
  && mkdir -p /opt/airflow/envs \
  && chown -R ${HOST_UID}:${HOST_GID} ${AIRFLOW_HOME}/ /opt/airflow/

RUN wget https://www.python.org/ftp/python/3.12.8/Python-3.12.8.tgz \
    && tar -xf Python-3.12.8.tgz \
    && cd Python-3.12.8 \
    && ./configure --enable-optimizations --with-ensurepip=install \
    && make -j$(nproc) \
    && make altinstall \
    && cd .. \
    && rm -rf Python-3.12.8 Python-3.12.8.tgz

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH "$PATH:/usr/bin/dirname"

COPY --chown=airflow scripts/entrypoint.sh /entrypoint.sh
COPY --chown=airflow pyproject.toml README.md scripts/requirements-vegetation-metrics.txt ${AIRFLOW_HOME}/
RUN chmod +x /entrypoint.sh

USER airflow

RUN curl -sSL https://install.python-poetry.org | python3

WORKDIR ${AIRFLOW_HOME}

RUN poetry config virtualenvs.create false \
  && poetry install --no-root --only main

RUN python3.12 -m venv /opt/airflow/envs/geospatial_env \
  && /opt/airflow/envs/geospatial_env/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
  && /opt/airflow/envs/geospatial_env/bin/pip install --no-cache-dir -r ${AIRFLOW_HOME}/requirements-vegetation-metrics.txt

ENTRYPOINT [ "/entrypoint.sh" ]
