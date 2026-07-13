import subprocess
import sys

import pandas as pd

from generate_paper_tables import build_paper_outputs, validate_input_sources


def test_paper_processing_sources_exist_and_validate_read_only():
    assert validate_input_sources() == []
    completed = subprocess.run(
        [sys.executable, "generate_paper_tables.py", "--check-only"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS" in completed.stdout


def test_generated_outputs_match_submitted_paper_and_use_display_names(tmp_path):
    build_paper_outputs(tmp_path, bootstrap_samples=500)

    expected = {
        "fig4_signature_width_data.csv",
        "fig5_population_scaling_data.csv",
        "fig5_id_length_data.csv",
        "fig6_epc_structure_data.csv",
        "fig7_ablation_data.csv",
        "table_iii_average_performance.csv",
        "table_iv_paired_bootstrap_ci.csv",
    }
    assert {path.name for path in tmp_path.glob("*.csv")} == expected

    table_iii = pd.read_csv(tmp_path / "table_iii_average_performance.csv")
    assert list(table_iii["Algorithm"]) == [
        "SGCT",
        "DRCT",
        "LAPCT",
        "EMDT",
        "DQTA",
        "EAQ-CBB",
        "NLHQT(n=2)",
    ]
    sgct = table_iii.loc[table_iii["Algorithm"] == "SGCT"].iloc[0]
    assert round(sgct["Identification time (s)"], 2) == 8.05
    assert round(sgct["Communication cost (bits/update)"], 2) == 114.27

    fig4 = pd.read_csv(tmp_path / "fig4_signature_width_data.csv")
    assert list(fig4["d"]) == [4, 6, 8, 10]
    assert round(fig4.loc[fig4["d"] == 10, "Identification time (s)"].iloc[0], 2) == 9.98

    fig5_id = pd.read_csv(tmp_path / "fig5_id_length_data.csv")
    assert 100 not in set(fig5_id["ID length (bits)"])
    assert set(fig5_id["ID length (bits)"]) == {20, 40, 60, 80, 96, 128, 160, 192, 256}

    fig7 = pd.read_csv(tmp_path / "fig7_ablation_data.csv")
    assert set(fig7["Variant"]) == {
        "SGCT (w/o marker pruning)",
        "SGCT (w/o local short-ID)",
    }
    marker = fig7.loc[fig7["Variant"] == "SGCT (w/o marker pruning)"].iloc[0]
    assert round(marker["Identification-time increase (%)"], 1) == 72.4
    assert round(marker["Communication-cost increase (%)"], 1) == 18.3

    table_iv = pd.read_csv(tmp_path / "table_iv_paired_bootstrap_ci.csv")
    assert "HT" + "-EEAC" not in set(table_iv["Baseline"])
    assert set(table_iv["Metric"]) == {"Identification time", "Communication cost"}


def test_ci_cli_can_check_inputs_without_writing():
    completed = subprocess.run(
        [
            sys.executable,
            "compute_paper_ci.py",
            "--raw-csv",
            "results_paper_final/formal_experiment10_algorithm_comparison/raw_runs.csv",
            "--check-only",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS" in completed.stdout
