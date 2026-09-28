"""Structural unit tests for the remaining AlertFlow DAGs."""

from __future__ import annotations

import unittest
from datetime import timedelta

from tests.dag_helpers import DAGS_DIR, load_dag_module

GEOSPATIAL_PYTHON = "/opt/airflow/envs/geospatial_env/bin/python"


class VegetationMetricsDagTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = load_dag_module(
            DAGS_DIR / "vegetation_metrics.py", "vegetation_metrics_dag"
        )
        cls.dag = module.vegetation_dag

    def test_metadata(self):
        self.assertEqual(self.dag.dag_id, "VEGETATION_INDEX_METRICS")
        self.assertEqual(self.dag.schedule, timedelta(days=16))
        self.assertTrue(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 4)

    def test_external_python_mapped_task(self):
        task = self.dag.get_task("run_state_pipeline")
        self.assertTrue(task.is_mapped)
        self.assertEqual(task.partial_kwargs["python"], GEOSPATIAL_PYTHON)

    def test_brazil_states_expansion(self):
        module = load_dag_module(
            DAGS_DIR / "vegetation_metrics.py", "vegetation_metrics_dag_2"
        )
        self.assertEqual(len(module.BRAZIL_STATES), 27)


class CopernicusBrasilDagTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        module = load_dag_module(
            DAGS_DIR / "satellite_weather" / "brasil.py",
            "copernicus_brasil_dag",
        )
        cls.dag = module.dag

    def test_metadata(self):
        self.assertEqual(self.dag.dag_id, "COPERNICUS_BRASIL")
        self.assertEqual(self.dag.schedule, "@daily")
        self.assertTrue(self.dag.catchup)
        self.assertEqual(self.dag.max_active_runs, 4)

    def test_task_graph(self):
        self.assertEqual(set(self.dag.task_ids), {"fetch_weather"})


if __name__ == "__main__":
    unittest.main()
