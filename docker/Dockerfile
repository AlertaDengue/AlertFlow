FROM apache/airflow:2.5.3

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
    gcc \
    make \
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
    libsqlite3-dev \
    postgresql-client \
    wget \
    && rm -rf /var/lib/apt/lists/*


RUN addgroup --gid ${HOST_GID} airflow \
 && usermod -u ${HOST_UID} -g ${HOST_GID} -d /home/airflow -s /bin/bash airflow \
 && echo "airflow ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/airflow \
 && chmod 0440 /etc/sudoers.d/airflow \
 && chown -R ${HOST_UID}:${HOST_GID} ${AIRFLOW_HOME}/ /opt/airflow/

ENV PATH "$PATH:/home/airflow/.local/bin"
ENV PATH "$PATH:/usr/bin/dirname"


# Install Python 3.10
RUN curl https://www.python.org/ftp/python/3.10.8/Python-3.10.8.tgz -o /tmp/Python-3.10.8.tgz \
    && tar -zxvf /tmp/Python-3.10.8.tgz -C /tmp \
    && cd /tmp/Python-3.10.8 \
    && ./configure --prefix=/opt/py310 --enable-optimizations \
    && make install \
    && mkdir /opt/envs/ \
    && chown -R airflow /opt/py310 /opt/envs\
    && echo "alias python3.10=/opt/py310/bin/python3.10" >> /home/airflow/.bashrc

COPY --chown=airflow alertflow/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
COPY --chown=airflow docker/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER airflow

WORKDIR ${AIRFLOW_HOME}

# Create Python3.10 virtual env
RUN /usr/local/bin/python -m virtualenv /opt/envs/py310 --python="/opt/py310/bin/python3.10" \
    && sed -i "s/include-system-site-packages = false/include-system-site-packages = true/" /opt/envs/py310/pyvenv.cfg \
    && source /opt/envs/py310/bin/activate \
    && pip install \
        "satellite-weather-downloader >= 1.8.2" \
        psycopg2

ENTRYPOINT [ "/entrypoint.sh" ]
