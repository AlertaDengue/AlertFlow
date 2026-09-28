"""Check and update the PySUS S3 database mirrors.

PySUS requires Python <3.14, so it runs in its own interpreter
(``/opt/airflow/envs/pysus_env``) via ``@task.external_python``. The
``pysus.management`` package is excluded from the published wheel, so the
container installs PySUS from source and overlays that package.

The pipeline runs a dry-run ``check`` first and only ``apply`` (download,
convert, upload and catalog) the databases that actually need it. The
``SyncEngine`` is single-writer, so the DAG serialises runs
(``max_active_runs=1``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.sdk import Variable, task

PYSUS_PYTHON = "/opt/airflow/envs/pysus_env/bin/python"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
}

with DAG(
    dag_id="PYSUS_UPDATE",
    description="Check and update every PySUS S3 database mirror",
    start_date=datetime(2026, 9, 28, 3, 0),
    schedule="0 3 * * 1",
    catchup=False,
    max_active_runs=1,
    tags=["pysus", "s3", "databases"],
    default_args=default_args,
) as pysus_dag:

    @task
    def get_credentials() -> dict:
        access = Variable.get("pysus_s3_access_key", deserialize_json=True)
        secret = Variable.get("pysus_s3_secret_key", deserialize_json=True)
        token = Variable.get("pysus_dadosgov_token", deserialize_json=True)
        return {
            "access_key": access.get("PYSUS_S3_ACCESS_KEY", ""),
            "secret_key": secret.get("PYSUS_S3_SECRET_KEY", ""),
            "dadosgov_token": token.get("PYSUS_DADOSGOV_TOKEN", ""),
        }

    @task.external_python(python=PYSUS_PYTHON, task_id="check_databases")
    def check_databases(credentials: dict) -> dict:
        """Dry-run: classify every file as missing/outdated/current."""
        import logging

        from pysus.api.client import _run_sync
        from pysus.management.sync import SyncEngine

        log = logging.getLogger("pysus_update.check")

        engine = SyncEngine(
            access_key=credentials["access_key"],
            secret_key=credentials["secret_key"],
            dadosgov_token=credentials["dadosgov_token"],
        )

        async def _run() -> dict:
            await engine.__aenter__(lock=False)
            try:
                checks = await engine.check()
            finally:
                await engine.__aexit__(None, None, None)
            return {ds: check.summary() for ds, check in checks.items()}

        summary = _run_sync(_run())

        log.info("PySUS check finished for %d database(s)", len(summary))
        for dataset in sorted(summary):
            stats = summary[dataset]
            log.info(
                "  %-22s missing=%-6d outdated=%-6d current=%-6d%s",
                dataset,
                stats["missing"],
                stats["outdated"],
                stats["current"],
                "  [needs update]" if stats["needs_update"] else "",
            )

        pending = sorted(ds for ds, s in summary.items() if s["needs_update"])
        listing = ", ".join(pending)
        log.info("%d database(s) need updating: %s", len(pending), listing)
        return summary

    @task.external_python(python=PYSUS_PYTHON, task_id="apply_updates")
    def apply_updates(credentials: dict, check_summary: dict) -> dict:
        """Download, convert, upload and catalog the pending files."""
        import logging

        from pysus.api.client import _run_sync
        from pysus.management.sync import SyncEngine

        log = logging.getLogger("pysus_update.apply")

        pending = sorted(
            ds
            for ds, summary in (check_summary or {}).items()
            if summary.get("needs_update")
        )
        if not pending:
            log.info("All PySUS databases are up to date; nothing to apply.")
            return {"total": 0, "uploaded": 0, "failed": 0, "datasets": []}

        log.info(
            "Applying updates to %d database(s): %s",
            len(pending),
            ", ".join(pending),
        )

        counts: dict[str, int] = {}

        def on_outcome(outcome) -> None:
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
            if outcome.status in ("failed", "needs_token"):
                log.warning("[%s] %s", outcome.status, outcome.detail)
            processed = sum(counts.values())
            if processed % 100 == 0:
                breakdown = ", ".join(
                    f"{key}={value}" for key, value in sorted(counts.items())
                )
                log.info("progress: %d processed (%s)", processed, breakdown)

        engine = SyncEngine(
            access_key=credentials["access_key"],
            secret_key=credentials["secret_key"],
            dadosgov_token=credentials["dadosgov_token"],
        )

        async def _run() -> dict:
            async with engine:
                report = await engine.run(
                    datasets=pending,
                    workers=8,
                    ftp_connections=4,
                    on_outcome=on_outcome,
                )
            return report.summary()

        summary = _run_sync(_run())
        summary["datasets"] = pending
        log.info("PySUS apply finished: %s", summary)
        return summary

    credentials = get_credentials()
    check_result = check_databases(credentials)
    apply_updates(credentials, check_result)
