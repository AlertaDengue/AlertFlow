FROM apache/airflow:2.5.3

USER root

COPY --chown=airflow:airflow ${AIRFLOW_PROJ_DIR}/alertflow/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
COPY --chown=airflow:airflow ${AIRFLOW_PROJ_DIR}/docker/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER airflow

WORKDIR ${AIRFLOW_HOME}

RUN python3 -m pip install \
  plyvel \
  satellite-weather-downloader

ENTRYPOINT [ "/entrypoint.sh" ]
