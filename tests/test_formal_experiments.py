import copy
import subprocess
import sys

import formal_experiment as formal
from algorithm_base_config import PAPER_ALGORITHMS


EXPECTED_EXPERIMENTS = [
    "formal_sgct_signature_sensitivity",
    "formal_main_scalability_uniform",
    "formal_id_length_sweep",
    "formal_experiment10_algorithm_comparison",
    "formal_experiment13_sgct_signature_grouping",
]


def test_paper_experiment_registry_and_result_directories_are_exact():
    assert list(formal.PAPER_EXPERIMENTS) == EXPECTED_EXPERIMENTS
    assert formal.PAPER_EXPERIMENT_RESULT_DIRS == {
        name: f"results_paper_final/{name}" for name in EXPECTED_EXPERIMENTS
    }
    assert [item["name"] for item in formal.selected_experiments([], paper_only=True)] == EXPECTED_EXPERIMENTS


def test_paper_sweeps_match_manuscript_selection_without_altering_raw_data():
    scalability = formal.PAPER_EXPERIMENTS["formal_main_scalability_uniform"]
    assert scalability["parameter_points"] == [
        {"TOTAL_TAGS": value} for value in range(1000, 10001, 1000)
    ]
    id_sweep = formal.PAPER_EXPERIMENTS["formal_id_length_sweep"]
    assert [point["BINARY_LENGTH"] for point in id_sweep["parameter_points"]] == [
        20, 40, 60, 80, 96, 128, 160, 192, 256
    ]
    sensitivity = formal.PAPER_EXPERIMENTS["formal_sgct_signature_sensitivity"]
    assert sensitivity["algorithm_parameter_points"] == [
        {"sgct_d_target": 4, "signature_slot_cap": 256},
        {"sgct_d_target": 6, "signature_slot_cap": 256},
        {"sgct_d_target": 8, "signature_slot_cap": 256},
        {"sgct_d_target": 10, "signature_slot_cap": 1024},
    ]


def test_paired_tasks_reuse_identical_tags_and_seeds_across_algorithms():
    experiment = copy.deepcopy(
        formal.PAPER_EXPERIMENTS["formal_main_scalability_uniform"]
    )
    experiment["parameter_points"] = [{"TOTAL_TAGS": 8}]
    experiment["scenario_config"]["BINARY_LENGTH"] = 8
    tasks = formal.build_paired_tasks(experiment, PAPER_ALGORITHMS[:2], 1, 1234)

    assert len(tasks) == 2
    assert tasks[0].tag_ids == tasks[1].tag_ids
    assert tasks[0].point_seed == tasks[1].point_seed
    assert tasks[0].algorithm_seed != tasks[1].algorithm_seed


def test_ablation_experiment_exposes_only_paper_variants():
    assert formal.algorithms_for_experiment(
        "formal_experiment13_sgct_signature_grouping", []
    ) == [
        "SGCT",
        "SGCT(no_signature_grouping)",
        "SGCT(no_local_short_id)",
    ]
    assert formal.algorithms_for_experiment(
        "formal_experiment10_algorithm_comparison", []
    ) == PAPER_ALGORITHMS


def test_read_only_cli_commands_validate_without_running_simulations():
    listed = subprocess.run(
        [sys.executable, "formal_experiment.py", "--list-paper-experiments"],
        check=True,
        capture_output=True,
        text=True,
    )
    for name in EXPECTED_EXPERIMENTS:
        assert name in listed.stdout
        assert f"results_paper_final/{name}" in listed.stdout

    validated = subprocess.run(
        [sys.executable, "formal_experiment.py", "--validate-paper-config"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PASS" in validated.stdout
    assert "7 paper algorithms" in validated.stdout
