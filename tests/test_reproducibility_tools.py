import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from compute_paper_ci import compute_ci_table
from generate_paper_tables import compact_algorithm_table
from formal_experiment import (
    ALGORITHM_LIBRARY,
    build_config_snapshot,
    deduplicate_result_columns,
)


class ReproducibilityToolsTest(unittest.TestCase):
    def test_deduplicate_result_columns_drops_equal_pandas_suffixes(self):
        df = pd.DataFrame(
            {
                "metric": [1.0, 2.0],
                "metric.1": [1.0, 2.0],
                "other.1": [3.0, 4.0],
            }
        )

        cleaned = deduplicate_result_columns(df)

        self.assertIn("metric", cleaned.columns)
        self.assertNotIn("metric.1", cleaned.columns)
        self.assertIn("other.1", cleaned.columns)

    def test_config_snapshot_records_drct_final_note(self):
        df = pd.DataFrame(
            {
                "experiment_name": ["unit"],
                "algorithm_name": ["DRCT"],
                "run_id": [0],
                "scenario_point": ["scenario_label=random"],
                "TOTAL_TAGS": [8],
                "BINARY_LENGTH": [16],
            }
        )
        experiment = {
            "name": "unit",
            "varying_param_key": "scenario_point",
            "scenario_config": {"TOTAL_TAGS": 8, "BINARY_LENGTH": 16},
            "algorithm_specific_config": {"ber": 0.0},
        }

        snapshot = build_config_snapshot(df, experiment, ALGORITHM_LIBRARY)

        self.assertIn("DRCT", snapshot["algorithms"])
        self.assertEqual("DRCTFinalAlgorithm", snapshot["algorithm_configs"]["DRCT"]["class"])
        self.assertIn("DRCTFinalAlgorithm", snapshot["drct_note"])
        json.dumps(snapshot)

    def test_compute_paper_ci_uses_paired_observations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw = Path(temp_dir) / "raw_runs.csv"
            pd.DataFrame(
                [
                    {"scenario_point": "a", "run_id": 0, "algorithm_name": "SGCT", "total_protocol_time_ms": 5.0},
                    {"scenario_point": "a", "run_id": 0, "algorithm_name": "DRCT", "total_protocol_time_ms": 10.0},
                    {"scenario_point": "a", "run_id": 1, "algorithm_name": "SGCT", "total_protocol_time_ms": 6.0},
                    {"scenario_point": "a", "run_id": 1, "algorithm_name": "DRCT", "total_protocol_time_ms": 12.0},
                ]
            ).to_csv(raw, index=False)

            result = compute_ci_table(raw, baselines=["DRCT"], bootstrap_samples=100, seed=1)

        bootstrap = result[result["method"] == "paired_bootstrap_aggregate_mean_reduction"].iloc[0]
        self.assertEqual(2, bootstrap["n"])
        self.assertAlmostEqual(50.0, bootstrap["mean_reduction_pct"])

    def test_compact_algorithm_table_reports_aggregate_gamma_b(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw = Path(temp_dir) / "raw_runs.csv"
            pd.DataFrame(
                [
                    {
                        "algorithm_name": "SGCT",
                        "total_protocol_time_ms": 10.0,
                        "throughput_tags_per_sec": 100.0,
                        "avg_total_bits": 10.0,
                        "system_efficiency": 0.5,
                    },
                    {
                        "algorithm_name": "SGCT",
                        "total_protocol_time_ms": 20.0,
                        "throughput_tags_per_sec": 300.0,
                        "avg_total_bits": 100.0,
                        "system_efficiency": 0.7,
                    },
                ]
            ).to_csv(raw, index=False)

            table = compact_algorithm_table(raw, ["SGCT"])

        row = table.iloc[0]
        self.assertAlmostEqual(400.0 / 110.0, row["gamma_B_aggregate"])
        self.assertAlmostEqual(6.5, row["gamma_B_run_mean"])
        self.assertIn("Rank", table.columns)


if __name__ == "__main__":
    unittest.main()
