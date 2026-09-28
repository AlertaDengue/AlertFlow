"""Helpers to load and exercise AlertFlow DAGs in unit tests.

Airflow is imported lazily so the test environment can be configured first:
DAG files are loaded directly from disk (no DagBag, no metadata DB) with
``Variable.get`` patched, and PySUS is replaced by an in-memory stub so the
external-interpreter task bodies can run in-process.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
DAGS_DIR = REPO_ROOT / "alertflow" / "dags"

os.environ["AIRFLOW_HOME"] = tempfile.mkdtemp(prefix="alertflow-airflow-home-")
os.environ["AIRFLOW__CORE__LOAD_EXAMPLES"] = "False"
os.environ["AIRFLOW__CORE__DAGS_FOLDER"] = str(DAGS_DIR)
os.environ["AIRFLOW__LOGGING__LOGGING_LEVEL"] = "INFO"

VARIABLES = {
    "psql_main_uri": {"PSQL_MAIN_URI": "postgresql://user:pass@host:5432/db"},
    "cdsapi_key": {"CDSAPI_KEY": "uid:key"},
    "pysus_s3_access_key": {"PYSUS_S3_ACCESS_KEY": "AKIA_TEST"},
    "pysus_s3_secret_key": {"PYSUS_S3_SECRET_KEY": "secret-test"},
    "pysus_dadosgov_token": {"PYSUS_DADOSGOV_TOKEN": "token-test"},
}


def _fake_variable_get(
    key,
    deserialize_json=False,
    default_var=None,
    **kwargs,
):
    if key in VARIABLES:
        return VARIABLES[key]
    if default_var is not None:
        return default_var
    raise KeyError(f"unexpected Variable.get({key!r})")


@contextmanager
def patched_variables():
    """Patch the Airflow Variable backends used by the DAGs."""
    from airflow.models import Variable as ModelVariable
    from airflow.sdk import Variable as SdkVariable

    sdk_get = staticmethod(_fake_variable_get)
    model_get = staticmethod(_fake_variable_get)
    sdk_patch = mock.patch.object(SdkVariable, "get", sdk_get)
    model_patch = mock.patch.object(ModelVariable, "get", model_get)
    with sdk_patch, model_patch:
        yield


def load_dag_module(path: Path, name: str) -> ModuleType:
    """Load a DAG file as a standalone module with variables patched."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load DAG module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    with patched_variables():
        spec.loader.exec_module(module)
    return module


class FakeDatabaseCheck:
    """Stand-in for ``pysus.management.records.DatabaseCheck``."""

    def __init__(self, missing=0, outdated=0, current=0):
        self._summary = {
            "missing": missing,
            "outdated": outdated,
            "current": current,
            "needs_update": bool(missing or outdated),
        }

    @property
    def needs_update(self):
        return self._summary["needs_update"]

    def summary(self):
        return dict(self._summary)


class FakeReport:
    """Stand-in for ``pysus.management.records.SyncReport``."""

    def __init__(self, outcomes):
        self._outcomes = outcomes

    def summary(self):
        counts = {
            "total": len(self._outcomes),
            "needs_update": 0,
            "uploaded": 0,
            "skipped": 0,
            "failed": 0,
            "needs_token": 0,
        }
        for outcome in self._outcomes:
            counts[outcome.status] = counts.get(outcome.status, 0) + 1
        return counts


class FakeSyncEngine:
    """Records how the DAG tasks drive the PySUS sync engine."""

    checks = {}
    instances = []

    def __init__(
        self,
        access_key=None,
        secret_key=None,
        dadosgov_token=None,
        **kwargs,
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.dadosgov_token = dadosgov_token
        self.enter_lock = "not-entered"
        self.check_datasets = "not-called"
        self.run_datasets = "not-called"
        FakeSyncEngine.instances.append(self)

    async def __aenter__(self, lock=True):
        self.enter_lock = lock
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def check(self, datasets=None):
        self.check_datasets = datasets
        return type(self).checks

    async def run(
        self,
        datasets=None,
        workers=16,
        ftp_connections=8,
        on_outcome=None,
        **kwargs,
    ):
        self.run_datasets = datasets
        self.workers = workers
        self.ftp_connections = ftp_connections
        outcomes = []
        for _ in range(99):
            outcomes.append(SimpleNamespace(status="uploaded", detail="file"))
        # one failure so the warning path is exercised as well
        outcomes.append(SimpleNamespace(status="failed", detail="boom"))
        if on_outcome is not None:
            for outcome in outcomes:
                on_outcome(outcome)
        return FakeReport(outcomes)


@contextmanager
def fake_pysus():
    """Install an in-memory ``pysus`` package for the duration of a test."""
    FakeSyncEngine.checks = {}
    FakeSyncEngine.instances = []
    modules = {
        "pysus": ModuleType("pysus"),
        "pysus.api": ModuleType("pysus.api"),
        "pysus.api.client": ModuleType("pysus.api.client"),
        "pysus.management": ModuleType("pysus.management"),
        "pysus.management.sync": ModuleType("pysus.management.sync"),
    }
    modules["pysus"].__path__ = []
    modules["pysus.api"].__path__ = []
    modules["pysus.management"].__path__ = []
    modules["pysus.api.client"]._run_sync = lambda coro: asyncio.run(coro)
    modules["pysus.management.sync"].SyncEngine = FakeSyncEngine
    with mock.patch.dict(sys.modules, modules):
        yield FakeSyncEngine
