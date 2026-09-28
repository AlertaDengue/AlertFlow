"""Unit tests for the PYSUS_UPDATE DAG."""

from __future__ import annotations

import unittest

from tests import dag_helpers

DAG_FILE = dag_helpers.DAGS_DIR / "pysus_update.py"
EXTERNAL_PYTHON = "/opt/airflow/envs/pysus_env/bin/python"
CREDENTIALS = {
    "access_key": "a",
    "secret_key": "s",
    "dadosgov_token": "t",
}


class PysusUpdateDagTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = dag_helpers.load_dag_module(DAG_FILE, "pysus_update_dag")
        cls.dag = module.pysus_dag

    def task(self, task_id):
        return self.dag.get_task(task_id)

    def test_metadata(self):
        self.assertEqual(self.dag.dag_id, "PYSUS_UPDATE")
        self.assertEqual(self.dag.schedule, "0 3 * * 1")
        self.assertFalse(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 1)

    def test_task_graph(self):
        self.assertEqual(
            set(self.dag.task_ids),
            {"get_credentials", "check_databases", "apply_updates"},
        )
        self.assertEqual(
            self.task("check_databases").upstream_task_ids,
            {"get_credentials"},
        )
        self.assertEqual(
            self.task("apply_updates").upstream_task_ids,
            {"get_credentials", "check_databases"},
        )
        self.assertEqual(
            self.task("get_credentials").downstream_task_ids,
            {"check_databases", "apply_updates"},
        )

    def test_external_interpreter(self):
        for task_id in ("check_databases", "apply_updates"):
            self.assertEqual(self.task(task_id).python, EXTERNAL_PYTHON)
        # get_credentials runs on the Airflow interpreter, not the venv.
        self.assertFalse(hasattr(self.task("get_credentials"), "python"))

    def test_get_credentials(self):
        with dag_helpers.patched_variables():
            result = self.task("get_credentials").python_callable()
        self.assertEqual(
            result,
            {
                "access_key": "AKIA_TEST",
                "secret_key": "secret-test",
                "dadosgov_token": "token-test",
            },
        )

    def test_check_databases_summary(self):
        with dag_helpers.fake_pysus() as engine_cls:
            sia_check = dag_helpers.FakeDatabaseCheck(
                missing=2,
                outdated=3,
                current=10,
            )
            engine_cls.checks = {
                "SIA": sia_check,
                "IBGE": dag_helpers.FakeDatabaseCheck(current=5),
            }
            check_task = self.task("check_databases")
            result = check_task.python_callable(CREDENTIALS)

        self.assertEqual(
            result["SIA"],
            {
                "missing": 2,
                "outdated": 3,
                "current": 10,
                "needs_update": True,
            },
        )
        self.assertEqual(
            result["IBGE"],
            {
                "missing": 0,
                "outdated": 0,
                "current": 5,
                "needs_update": False,
            },
        )

        engine = engine_cls.instances[-1]
        self.assertFalse(engine.enter_lock)
        self.assertIsNone(engine.check_datasets)
        self.assertEqual(
            (engine.access_key, engine.secret_key, engine.dadosgov_token),
            ("a", "s", "t"),
        )

    def test_apply_updates_runs_only_pending(self):
        with dag_helpers.fake_pysus() as engine_cls:
            result = self.task("apply_updates").python_callable(
                CREDENTIALS,
                {
                    "SIA": {"needs_update": True},
                    "IBGE": {"needs_update": False},
                },
            )

        engine = engine_cls.instances[-1]
        self.assertEqual(engine.run_datasets, ["SIA"])
        self.assertEqual(result["total"], 100)
        self.assertEqual(result["uploaded"], 99)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["datasets"], ["SIA"])

    def test_apply_updates_skips_when_current(self):
        with dag_helpers.fake_pysus() as engine_cls:
            result = self.task("apply_updates").python_callable(
                CREDENTIALS, {"IBGE": {"needs_update": False}}
            )

        self.assertEqual(
            result,
            {"total": 0, "uploaded": 0, "failed": 0, "datasets": []},
        )
        self.assertEqual(engine_cls.instances, [])

    def test_apply_updates_logs_progress(self):
        logs_ctx = self.assertLogs("pysus_update.apply", level="INFO")
        with dag_helpers.fake_pysus(), logs_ctx as logs:
            self.task("apply_updates").python_callable(
                CREDENTIALS, {"SIA": {"needs_update": True}}
            )

        output = "\n".join(logs.output)
        self.assertIn("Applying updates to 1 database(s): SIA", output)
        self.assertIn("progress: 100 processed", output)
        self.assertIn("[failed] boom", output)


if __name__ == "__main__":
    unittest.main()
