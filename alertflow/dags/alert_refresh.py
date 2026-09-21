from __future__ import annotations

from datetime import timedelta
from typing import Any

import pendulum
from airflow.providers.standard.operators.trigger_dagrun import (
    TriggerDagRunOperator,
)
from airflow.sdk import DAG, Variable, task
from sqlalchemy import create_engine, text


DAG_ID_DISPATCHER = "SINAN_REFRESH_DISPATCHER"
DAG_ID_REFRESH = "ALERTA_REFRESH_FULL"

TARGET_UF = "BR"
REQUIRED_DISEASES = ("A90", "A92")

DEFAULT_ARGS = {
    "owner": "AlertaDengue",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}


def _pipeline_logical_date(delivery_se: int) -> str:
    """
    Build a deterministic logical date for one epidemiological week.

    The value is used only as an Airflow idempotency key. The actual
    epidemiological week passed to the analysis pipeline remains YYYYWW.
    """
    year = delivery_se // 100
    week = delivery_se % 100

    return (
        pendulum.datetime(
            year,
            1,
            1,
            tz="America/Sao_Paulo",
        )
        .add(weeks=week - 1)
        .to_iso8601_string()
    )


with DAG(
    dag_id=DAG_ID_DISPATCHER,
    description=(
        "Detect completed SINAN BR ingestion and dispatch the alert "
        "refresh workflow."
    ),
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(
        2026,
        9,
        21,
        tz="America/Sao_Paulo",
    ),
    schedule="*/5 * * * *",
    catchup=False,
    max_active_runs=1,
    tags=["sinan", "alerts", "dispatcher"],
) as dispatcher_dag:

    @task
    def find_ready_epiweek() -> dict[str, Any] | None:
        """
        Return the newest epiweek whose latest dengue and chikungunya
        ingestion runs are both completed.
        """
        db_config = Variable.get(
            "psql_main_uri",
            deserialize_json=True,
        )
        database_uri = db_config["PSQL_MAIN_URI"]

        query = text(
            """
            WITH latest_runs AS (
                SELECT
                    delivery_se,
                    disease,
                    status,
                    created_at,
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY delivery_se, disease
                        ORDER BY created_at DESC, id DESC
                    ) AS row_number
                FROM "ingestion"."run"
                WHERE uf = :uf
                  AND disease IN (:dengue, :chikungunya)
            ),
            ready_epiweeks AS (
                SELECT delivery_se
                FROM latest_runs
                WHERE row_number = 1
                GROUP BY delivery_se
                HAVING
                    COUNT(*) FILTER (
                        WHERE disease = :dengue
                          AND status = 'completed'
                    ) = 1
                    AND
                    COUNT(*) FILTER (
                        WHERE disease = :chikungunya
                          AND status = 'completed'
                    ) = 1
            )
            SELECT delivery_se
            FROM ready_epiweeks
            ORDER BY delivery_se DESC
            LIMIT 1
            """
        )

        engine = create_engine(
            database_uri,
            pool_pre_ping=True,
        )

        try:
            with engine.connect() as connection:
                row = (
                    connection.execute(
                        query,
                        {
                            "uf": TARGET_UF,
                            "dengue": REQUIRED_DISEASES[0],
                            "chikungunya": REQUIRED_DISEASES[1],
                        },
                    )
                    .mappings()
                    .first()
                )
        finally:
            engine.dispose()

        if row is None:
            print(
                "No epidemiological week is ready for alert refresh."
            )
            return None

        delivery_se = int(row["delivery_se"])
        week = str(delivery_se)

        result = {
            "week": week,
            "logical_date": _pipeline_logical_date(delivery_se),
        }

        print(f"Ready epiweek detected: {result}")
        return result

    @task.short_circuit()
    def has_ready_epiweek(
        candidate: dict[str, Any] | None,
    ) -> bool:
        """
        Stop the dispatcher cleanly when ingestion is not ready.
        """
        return candidate is not None

    candidate = find_ready_epiweek()
    ready = has_ready_epiweek(candidate)

    trigger_refresh = TriggerDagRunOperator(
        task_id="trigger_alert_refresh_full",
        trigger_dag_id=DAG_ID_REFRESH,
        trigger_run_id=(
            "alerta_refresh_full__"
            "{{ ti.xcom_pull("
            "task_ids='find_ready_epiweek'"
            ")['week'] }}"
        ),
        conf={
            "week": (
                "{{ ti.xcom_pull("
                "task_ids='find_ready_epiweek'"
                ")['week'] }}"
            ),
            "cores": 8,
        },
        logical_date=(
            "{{ ti.xcom_pull("
            "task_ids='find_ready_epiweek'"
            ")['logical_date'] }}"
        ),
        wait_for_completion=False,
        skip_when_already_exists=True,
        fail_when_dag_is_paused=True,
    )

    ready >> trigger_refresh

with DAG(
    dag_id=DAG_ID_REFRESH,
    description="Run the complete weekly AlertaDengue alert refresh.",
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(
        2026,
        9,
        21,
        tz="America/Sao_Paulo",
    ),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    params={
        "week": "",
        "cores": 8,
    },
    tags=["alerts", "analysis"],
) as refresh_dag:

    @task
    def validate_refresh_request() -> dict[str, Any]:
        """
        Validate parameters passed by the dispatcher or manual execution.
        """
        from airflow.sdk import get_current_context

        context = get_current_context()

        dag_run = context.get("dag_run")
        params = context.get("params", {})

        conf = {}
        if dag_run is not None and dag_run.conf:
            conf = dag_run.conf

        week = str(
            conf.get(
                "week",
                params.get("week", ""),
            )
        ).strip()

        cores = int(
            conf.get(
                "cores",
                params.get("cores", 8),
            )
        )

        if not week.isdigit() or len(week) != 6:
            raise ValueError(
                "week must use the YYYYWW format"
            )

        year = int(week[:4])
        epiweek = int(week[4:])

        if year < 2000 or year > 2100:
            raise ValueError(
                f"Invalid epidemiological year: {year}"
            )

        if epiweek < 1 or epiweek > 53:
            raise ValueError(
                f"Invalid epidemiological week: {epiweek}"
            )

        if cores < 1:
            raise ValueError(
                "cores must be greater than zero"
            )

        request = {
            "week": week,
            "cores": cores,
        }

        print(
            f"Validated alert refresh request: {request}"
        )

        return request

    validate_refresh_request()
