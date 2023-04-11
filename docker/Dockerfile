FROM apache/airflow:2.5.3

USER root

COPY --chown=airflow alertflow/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
COPY --chown=airflow docker/scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER airflow

WORKDIR ${AIRFLOW_HOME}

ENTRYPOINT [ "/entrypoint.sh" ]
