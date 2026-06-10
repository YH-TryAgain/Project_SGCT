import unittest

from Framework import Tag, generate_scenario, run_simulation_with_tags
from formal_experiment import (
    DEFAULT_RUNS_PER_POINT,
    EXPERIMENT12_HLCT_LIBRARY,
    EXTENDED_COMPARISON_ALGORITHMS,
    FORMAL_EXPERIMENTS,
    FORMAL_PAPER_EXPERIMENTS,
    OCG_ABLATION_LIBRARY,
    PAPER_BASELINE_ALGORITHMS,
    SGCT_ABLATION_LIBRARY,
    filter_missing_tasks,
    RESULTS_BASE_DIR,
    algorithm_library_for_experiment,
    algorithms_for_experiment,
    build_paired_tasks,
    calculate_paired_significance,
    metric_columns_for_summary,
    run_formal_task_for_experiment,
    selected_experiments,
)
from algorithm_base_config import ALGORITHM_LIBRARY


class FormalExperimentDesignTests(unittest.TestCase):
    def test_paired_tasks_reuse_identical_tags_across_algorithms(self):
        experiment = {
            "name": "unit_pairing",
            "varying_param_key": "TOTAL_TAGS",
            "varying_param_values": [8],
            "scenario_config": {
                "BINARY_LENGTH": 8,
                "id_distribution": "random",
            },
            "algorithm_specific_config": {"ber": 0.0},
        }

        tasks = build_paired_tasks(
            experiment=experiment,
            algorithms=["HLCT-Base", "DRCT"],
            runs_per_point=2,
            base_seed=700,
        )

        by_run = {}
        for task in tasks:
            key = (task.scenario_config["TOTAL_TAGS"], task.run_id)
            by_run.setdefault(key, []).append(task)

        self.assertEqual(2, len(by_run))
        for paired_tasks in by_run.values():
            self.assertEqual(2, len(paired_tasks))
            self.assertEqual(
                paired_tasks[0].tag_ids,
                paired_tasks[1].tag_ids,
                "Algorithms in the same point/run must use the same tag set",
            )

        run0_tags = by_run[(8, 0)][0].tag_ids
        run1_tags = by_run[(8, 1)][0].tag_ids
        self.assertNotEqual(run0_tags, run1_tags)

    def test_simulation_can_use_explicit_tags(self):
        tags = [Tag("0000"), Tag("0001"), Tag("0010"), Tag("1010")]
        info = ALGORITHM_LIBRARY["HLCT-Base"]
        config = dict(info["config"])
        config["ber"] = 0.0

        result = run_simulation_with_tags(tags, info["class"], config)

        self.assertEqual(4, result["identified_tags_count"])

    def test_energy_model_parameters_are_recorded_as_separate_components(self):
        tags = [Tag("0000"), Tag("0001"), Tag("0010"), Tag("1010")]
        info = ALGORITHM_LIBRARY["SGCT"]
        base_config = {
            **info["config"],
            "ber": 0.0,
            "enable_refined_energy_model": True,
        }

        baseline = run_simulation_with_tags(tags, info["class"], base_config)
        tag_expensive = run_simulation_with_tags(
            tags,
            info["class"],
            {**base_config, "tag_tx_energy_per_bit_nj": 1.0},
        )

        self.assertEqual(baseline["identified_tags_count"], tag_expensive["identified_tags_count"])
        self.assertGreater(tag_expensive["total_tag_tx_energy_uj"], baseline["total_tag_tx_energy_uj"])
        self.assertIn("energy_per_tag_uj", tag_expensive)

    def test_prefix_length_sweep_is_part_of_formal_experiments(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_common_prefix_sweep", experiments)
        sweep = experiments["formal_common_prefix_sweep"]
        self.assertEqual("scenario_point", sweep["varying_param_key"])
        grid = {item["key"]: item["values"] for item in sweep["varying_params"]}
        self.assertEqual([1000, 2000, 5000, 10000], grid["TOTAL_TAGS"])
        self.assertNotIn(88, grid["prefix_length"])
        self.assertIn(72, grid["prefix_length"])

    def test_inspect_window_sensitivity_is_part_of_formal_experiments(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_inspect_window_sensitivity", experiments)
        self.assertEqual(
            "algorithm",
            experiments["formal_inspect_window_sensitivity"]["varying_param_target"],
        )

    def test_fcw_window_sensitivity_is_part_of_formal_experiments(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_fcw_window_sensitivity", experiments)
        experiment = experiments["formal_fcw_window_sensitivity"]
        self.assertEqual("scenario_point", experiment["varying_param_key"])
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertEqual([0, 2, 4, 6, 8, 12, 16], grid["fused_window_bits"])
        self.assertIn("prefix64", grid["scenario_label"])
        self.assertIn("prefix72", grid["scenario_label"])
        self.assertIn("prefix80", grid["scenario_label"])
        self.assertIn("clustered", grid["scenario_label"])

    def test_ovg_stress_ablation_is_part_of_formal_experiments(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_ovg_stress_ablation", experiments)
        experiment = experiments["formal_ovg_stress_ablation"]
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertEqual(["prefix64", "prefix72", "prefix80", "dispersed", "clustered"], grid["scenario_label"])

        tasks = build_paired_tasks(
            experiment=experiment,
            algorithms=["HLCT-Base"],
            runs_per_point=1,
            base_seed=700,
        )
        self.assertGreater(len(tasks), 0)

    def test_check_gating_ablation_is_part_of_formal_experiments(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_check_gating_ablation", experiments)
        experiment = experiments["formal_check_gating_ablation"]
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertIn("prefix80", grid["scenario_label"])
        self.assertIn("clustered", grid["scenario_label"])

    def test_full_algorithm_comparison_is_part_of_formal_experiments(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_full_algorithm_comparison", experiments)
        experiment = experiments["formal_full_algorithm_comparison"]
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertIn("clustered", grid["scenario_label"])
        self.assertIn("prefix80", grid["scenario_label"])

    def test_experiment10_comparison_uses_requested_algorithm_set(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_experiment10_algorithm_comparison", experiments)
        experiment = experiments["formal_experiment10_algorithm_comparison"]
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertEqual(
            ["random", "prefixed", "prefix64", "prefix72", "prefix80", "dispersed", "sequential", "clustered"],
            grid["scenario_label"],
        )
        self.assertEqual(10000, experiment["scenario_config"]["TOTAL_TAGS"])
        self.assertEqual(
            [
                "SGCT",
                "DRCT",
                "LAPCT",
                "DQTA(k_max=3)",
                "EMDT",
                "NLHQT(n=2)",
                "EAQ_CBB",
                "HT_EEAC",
            ],
            algorithms_for_experiment("formal_experiment10_algorithm_comparison", []),
        )
        self.assertNotIn("HLCT-Base", algorithms_for_experiment("formal_experiment10_algorithm_comparison", []))

    def test_experiment13_progressive_signature_grouping_is_configured(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_experiment13_sgct_signature_grouping", experiments)
        experiment = experiments["formal_experiment13_sgct_signature_grouping"]
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertEqual(
            ["random", "prefixed", "prefix64", "prefix72", "prefix80", "dispersed", "sequential", "clustered"],
            grid["scenario_label"],
        )
        self.assertEqual(10000, experiment["scenario_config"]["TOTAL_TAGS"])
        self.assertEqual(
            [
                "SGCT",
                "HLCT-Base",
                "SGCT(no_signature_grouping)",
                "SGCT(no_local_short_id)",
                "SGCT(no_suffix_extension)",
                "SGCT(no_low_d_fallback)",
                "SGCT(d4)",
                "SGCT(d6)",
                "SGCT(d8)",
                "SGCT(d10)",
                "EMDT",
                "NLHQT(n=2)",
                "DRCT",
                "LAPCT",
                "DQTA(k_max=3)",
            ],
            algorithms_for_experiment("formal_experiment13_sgct_signature_grouping", []),
        )

    def test_experiment13_algorithm_library_contains_every_selected_algorithm(self):
        selected = algorithms_for_experiment("formal_experiment13_sgct_signature_grouping", [])
        library = algorithm_library_for_experiment("formal_experiment13_sgct_signature_grouping")

        self.assertFalse([name for name in selected if name not in library])

    def test_experiment_specific_worker_runs_sg_ablation_variant(self):
        experiment = {
            "name": "formal_experiment13_sgct_signature_grouping",
            "varying_param_key": "scenario_point",
            "varying_params": [
                {"key": "scenario_label", "target": "scenario", "values": ["random"]},
            ],
            "scenario_config": {
                "TOTAL_TAGS": 8,
                "BINARY_LENGTH": 16,
            },
            "algorithm_specific_config": {"ber": 0.0},
        }
        task = build_paired_tasks(
            experiment=experiment,
            algorithms=["SGCT(no_signature_grouping)"],
            runs_per_point=1,
            base_seed=700,
        )[0]

        result, _, algorithm_name, _ = run_formal_task_for_experiment(task)

        self.assertEqual("SGCT(no_signature_grouping)", algorithm_name)
        self.assertEqual(8, result["identified_tags_count"])

    def test_sgct_formal_experiment_family_is_available(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}
        for name in [
            "formal_sgct_scalability",
            "formal_sgct_prefix_sweep",
            "formal_sgct_signature_sensitivity",
            "formal_sgct_ber_robustness",
            "formal_sgct_id_length_structured",
            "formal_sgct_energy_sensitivity",
            "formal_extended_baseline_screen",
        ]:
            self.assertIn(name, experiments)

        scalability = experiments["formal_sgct_scalability"]
        grid = {item["key"]: item["values"] for item in scalability["varying_params"]}
        self.assertEqual([1000, 2000, 3000, 5000, 7000, 10000], grid["TOTAL_TAGS"])
        self.assertEqual(["random", "prefixed", "clustered", "sequential"], grid["scenario_label"])

        ber = experiments["formal_sgct_ber_robustness"]
        grid = {item["key"]: item["values"] for item in ber["varying_params"]}
        self.assertEqual([0.0, 1e-5, 1e-4, 1e-3], grid["ber"])
        self.assertEqual(["random", "prefix80", "clustered", "dispersed", "sequential"], grid["scenario_label"])
        self.assertEqual(10000, ber["scenario_config"]["TOTAL_TAGS"])

        prefix = experiments["formal_sgct_prefix_sweep"]
        grid = {item["key"]: item["values"] for item in prefix["varying_params"]}
        self.assertIn(88, grid["prefix_length"])
        self.assertEqual([100, 1000, 10000], grid["TOTAL_TAGS"])

        signature = experiments["formal_sgct_signature_sensitivity"]
        grid = {item["key"]: item["values"] for item in signature["varying_params"]}
        self.assertEqual([4, 6, 8, 10], grid["sgct_d_target"])
        self.assertEqual([256, 512, 1024], grid["signature_slot_cap"])
        self.assertEqual(10000, signature["scenario_config"]["TOTAL_TAGS"])

        id_length = experiments["formal_sgct_id_length_structured"]
        grid = {item["key"]: item["values"] for item in id_length["varying_params"]}
        self.assertEqual([64, 96, 128, 160], grid["BINARY_LENGTH"])
        self.assertEqual(["random", "medium-prefix", "long-prefix", "clustered"], grid["scenario_label"])

        energy = experiments["formal_sgct_energy_sensitivity"]
        grid = {item["key"]: item["values"] for item in energy["varying_params"]}
        self.assertEqual(
            ["baseline", "tag-expensive", "reader-expensive", "listen-expensive", "balanced-high"],
            grid["energy_profile"],
        )

    def test_prefix_sweep_includes_feasible_eighty_eight_bit_points_only(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        tasks = build_paired_tasks(
            experiment=experiments["formal_sgct_prefix_sweep"],
            algorithms=["SGCT"],
            runs_per_point=1,
            base_seed=700,
        )

        prefix88_tasks = [
            task for task in tasks if "prefix_length=88" in task.scenario_config["scenario_point"]
        ]
        self.assertTrue(prefix88_tasks)
        self.assertTrue(all(task.scenario_config["TOTAL_TAGS"] <= 100 for task in prefix88_tasks))

    def test_sgct_experiments_compare_against_other_algorithm_families(self):
        expected_core = [
            "SGCT",
            "EMDT",
            "NLHQT(n=2)",
            "DRCT",
            "LAPCT",
            "DQTA(k_max=3)",
            "EAQ_CBB",
            "HT_EEAC",
        ]

        for name in [
            "formal_experiment10_algorithm_comparison",
            "formal_sgct_scalability",
            "formal_sgct_prefix_sweep",
            "formal_sgct_ber_robustness",
        ]:
            selected = algorithms_for_experiment(name, [])
            for algorithm_name in expected_core:
                self.assertIn(algorithm_name, selected)
            self.assertNotIn("BGCT", selected)
            self.assertNotIn("BGCT_Random", selected)

    def test_extended_comparison_set_includes_recent_registered_baselines(self):
        for name in ["EAQ_CBB", "HT_EEAC", "ICT", "SD-CGQT", "SUBF-CGDFSA"]:
            self.assertIn(name, EXTENDED_COMPARISON_ALGORITHMS)
        self.assertNotIn("BGCT_Random", EXTENDED_COMPARISON_ALGORITHMS)
        self.assertEqual(
            EXTENDED_COMPARISON_ALGORITHMS,
            algorithms_for_experiment("formal_extended_baseline_screen", []),
        )

    def test_sgct_ablation_library_contains_module_and_d_variants(self):
        expected = [
            "SGCT",
            "SGCT(no_signature_grouping)",
            "SGCT(no_local_short_id)",
            "SGCT(no_suffix_extension)",
            "SGCT(no_low_d_fallback)",
            "SGCT(d4)",
            "SGCT(d6)",
            "SGCT(d8)",
            "SGCT(d10)",
        ]

        self.assertEqual(expected, list(SGCT_ABLATION_LIBRARY.keys()))
        self.assertFalse(SGCT_ABLATION_LIBRARY["SGCT(no_signature_grouping)"]["config"]["enable_signature_grouping"])
        self.assertFalse(
            SGCT_ABLATION_LIBRARY["SGCT(no_local_short_id)"]["config"]["enable_local_short_id"]
        )
        self.assertFalse(
            SGCT_ABLATION_LIBRARY["SGCT(no_suffix_extension)"]["config"]["enable_suffix_signature"]
        )
        self.assertFalse(
            SGCT_ABLATION_LIBRARY["SGCT(no_low_d_fallback)"]["config"]["enable_low_d_fallback"]
        )
        self.assertNotIn("SGCT(hash_short_id)", SGCT_ABLATION_LIBRARY)

    def test_sgct_new_supplement_experiments_use_requested_algorithm_sets(self):
        self.assertEqual(
            ["SGCT", "NLHQT(n=2)", "EMDT", "DQTA(k_max=3)", "DRCT", "LAPCT"],
            algorithms_for_experiment("formal_sgct_id_length_structured", []),
        )
        self.assertEqual(
            ["SGCT", "NLHQT(n=2)", "EMDT", "DQTA(k_max=3)"],
            algorithms_for_experiment("formal_sgct_energy_sensitivity", []),
        )

    def test_resume_existing_filters_completed_rows_only(self):
        pd = __import__("pandas")
        experiment = {
            "name": "unit_resume",
            "varying_param_key": "scenario_point",
            "varying_params": [
                {"key": "scenario_label", "target": "scenario", "values": ["random"]},
            ],
            "scenario_config": {
                "TOTAL_TAGS": 8,
                "BINARY_LENGTH": 16,
            },
            "algorithm_specific_config": {"ber": 0.0},
        }
        tasks = build_paired_tasks(
            experiment=experiment,
            algorithms=["SGCT", "EMDT"],
            runs_per_point=2,
            base_seed=700,
        )
        existing = pd.DataFrame(
            [
                {"algorithm_name": "SGCT", "run_id": 0, "scenario_point": "scenario_label=random"},
                {"algorithm_name": "EMDT", "run_id": 0, "scenario_point": "scenario_label=random"},
                {"algorithm_name": "SGCT", "run_id": 1, "scenario_point": "scenario_label=random"},
            ]
        )

        missing = filter_missing_tasks(tasks, existing, "scenario_point")

        self.assertEqual(1, len(missing))
        self.assertEqual("EMDT", missing[0].algorithm_name)
        self.assertEqual(1, missing[0].run_id)

    def test_experiment11_hlct_improvement_ablation_is_available(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_experiment11_hlct_improvement", experiments)
        experiment = experiments["formal_experiment11_hlct_improvement"]
        grid = {item["key"]: item["values"] for item in experiment["varying_params"]}
        self.assertEqual(
            ["random", "prefixed", "prefix80", "dispersed", "clustered"],
            grid["scenario_label"],
        )
        self.assertEqual(
            [
                "HLCT-Base",
                "HLCT-Base(prev_R2)",
                "HLCT-Base(no_ovg)",
                "HLCT-Base(adaptive_fcw)",
                "HLCT-Base(no_prefix_stagnation)",
            ],
            algorithms_for_experiment("formal_experiment11_hlct_improvement", []),
        )

    def test_registered_library_keeps_extended_algorithms_available(self):
        for name in ["ICT", "SD-CGQT", "SUBF-CGDFSA"]:
            self.assertIn(name, ALGORITHM_LIBRARY)
        self.assertNotIn("BGCT", ALGORITHM_LIBRARY)
        self.assertNotIn("BGCT_Random", ALGORITHM_LIBRARY)

    def test_ovg_metrics_are_in_formal_summary(self):
        columns = metric_columns_for_summary(
            __import__("pandas").DataFrame(
                columns=[
                    "ovg_success_count",
                    "post_ovg_singleton_count",
                    "ovg_fallback_avoid_count",
                    "prefix_stag_score_trigger_count",
                    "repeated_pattern_trigger_count",
                ]
            )
        )

        self.assertIn("ovg_success_count", columns)
        self.assertIn("post_ovg_singleton_count", columns)
        self.assertIn("ovg_fallback_avoid_count", columns)
        self.assertIn("prefix_stag_score_trigger_count", columns)
        self.assertIn("repeated_pattern_trigger_count", columns)

    def test_algorithm_targeted_varying_param_goes_to_algorithm_config(self):
        experiment = {
            "name": "unit_algorithm_param",
            "varying_param_key": "inspect_window_bits",
            "varying_param_target": "algorithm",
            "varying_param_values": [8],
            "scenario_config": {
                "TOTAL_TAGS": 8,
                "BINARY_LENGTH": 16,
                "id_distribution": "random",
            },
            "algorithm_specific_config": {"ber": 0.0},
        }

        task = build_paired_tasks(
            experiment=experiment,
            algorithms=["HLCT-Base"],
            runs_per_point=1,
            base_seed=700,
        )[0]

        self.assertNotIn("inspect_window_bits", task.scenario_config)
        self.assertEqual(8, task.algorithm_specific_config["inspect_window_bits"])

    def test_multi_param_grid_builds_scenario_point_and_filters_invalid_points(self):
        experiment = {
            "name": "unit_grid",
            "varying_param_key": "scenario_point",
            "varying_params": [
                {"key": "TOTAL_TAGS", "target": "scenario", "values": [4, 8]},
                {"key": "prefix_length", "target": "scenario", "values": [2]},
            ],
            "scenario_config": {
                "BINARY_LENGTH": 4,
                "id_distribution": "prefixed",
            },
            "algorithm_specific_config": {"ber": 0.0},
        }

        tasks = build_paired_tasks(
            experiment=experiment,
            algorithms=["HLCT-Base"],
            runs_per_point=1,
            base_seed=700,
        )

        self.assertEqual(1, len(tasks))
        self.assertEqual(4, tasks[0].scenario_config["TOTAL_TAGS"])
        self.assertEqual("TOTAL_TAGS=4,prefix_length=2", tasks[0].scenario_config["scenario_point"])

    def test_no_check_escalation_ablation_keeps_default_check_bits(self):
        config = OCG_ABLATION_LIBRARY["HLCT-Base(no_check_escalation)"]["config"]

        self.assertEqual(4, config["f_default"])
        self.assertEqual(4, config["f_escalated"])

    def test_no_check_gating_ablation_disables_check_gating(self):
        config = OCG_ABLATION_LIBRARY["HLCT-Base(no_check_gating)"]["config"]

        self.assertFalse(config["enable_check_gating"])

    def test_no_ovg_ablation_disables_ovg(self):
        config = OCG_ABLATION_LIBRARY["HLCT-Base(no_ovg)"]["config"]

        self.assertFalse(config["enable_ovg"])

    def test_no_prefix_stagnation_ablation_disables_prefix_stagnation(self):
        config = OCG_ABLATION_LIBRARY["HLCT-Base(no_prefix_stagnation)"]["config"]

        self.assertFalse(config["enable_prefix_stagnation"])

    def test_fixed_8bit_check_ablation_uses_fixed_eight_bit_check(self):
        config = OCG_ABLATION_LIBRARY["HLCT-Base(fixed_8bit_check)"]["config"]

        self.assertEqual(8, config["f_default"])
        self.assertEqual(8, config["f_escalated"])

    def test_cbit_only_ablation_sets_cbit_only_policy(self):
        config = OCG_ABLATION_LIBRARY["HLCT-Base(cbit_only)"]["config"]

        self.assertEqual("CBIT_ONLY", config["split_policy"])

    def test_clustered_scenario_generates_unique_ids(self):
        tags = generate_scenario(
            {
                "TOTAL_TAGS": 32,
                "BINARY_LENGTH": 32,
                "id_distribution": "clustered",
                "cluster_count": 4,
                "cluster_prefix_length": 20,
            }
        )

        self.assertEqual(32, len({tag.id for tag in tags}))

    def test_fcw_metrics_are_in_formal_summary(self):
        columns = metric_columns_for_summary(
            __import__("pandas").DataFrame(
                columns=[
                    "fcw_cache_created_count",
                    "fcw_cache_hit_count",
                    "fcw_cache_hit_ratio",
                    "inspect_collision_count",
                    "adaptive_cbit_r4_count",
                    "multibit_fallback_count",
                ]
            )
        )

        self.assertIn("fcw_cache_created_count", columns)
        self.assertIn("fcw_cache_hit_count", columns)
        self.assertIn("fcw_cache_hit_ratio", columns)
        self.assertIn("inspect_collision_count", columns)
        self.assertIn("adaptive_cbit_r4_count", columns)
        self.assertIn("multibit_fallback_count", columns)

    def test_sg_metrics_are_in_formal_summary(self):
        columns = metric_columns_for_summary(
            __import__("pandas").DataFrame(
                columns=[
                    "progressive_probe_count",
                    "signature_grouping_trigger_count",
                    "local_short_id_trigger_count",
                    "signature_groups_pruned",
                    "sparse_signature_groups",
                    "signature_marker_bits",
                    "signature_marker_tag_bits",
                    "signature_non_idle_marker_count",
                    "hash_short_id_round_count",
                    "hash_short_id_split_count",
                    "hash_short_id_collision_groups",
                    "hash_short_id_singleton_groups",
                    "small_cluster_guard_count",
                    "signature_singleton_groups",
                    "signature_collision_groups",
                    "low_d_fallback_count",
                    "suffix_signature_trigger_count",
                    "max_signature_d",
                    "epc_verification_count",
                    "verify_fail_count",
                    "avg_tag_responses",
                ]
            )
        )

        self.assertIn("signature_groups_pruned", columns)
        self.assertIn("signature_collision_groups", columns)
        self.assertIn("signature_marker_tag_bits", columns)
        self.assertIn("hash_short_id_round_count", columns)
        self.assertIn("hash_short_id_split_count", columns)
        self.assertIn("hash_short_id_collision_groups", columns)
        self.assertIn("small_cluster_guard_count", columns)
        self.assertIn("suffix_signature_trigger_count", columns)
        self.assertIn("max_signature_d", columns)
        self.assertIn("avg_tag_responses", columns)

    def test_paired_significance_reports_sg_comparisons(self):
        pd = __import__("pandas")
        df = pd.DataFrame(
            [
                {"scenario_point": "random", "algorithm_name": "SGCT", "run_id": 0, "total_protocol_time_ms": 8.0},
                {"scenario_point": "random", "algorithm_name": "HLCT-Base", "run_id": 0, "total_protocol_time_ms": 10.0},
                {"scenario_point": "random", "algorithm_name": "SGCT", "run_id": 1, "total_protocol_time_ms": 7.0},
                {"scenario_point": "random", "algorithm_name": "HLCT-Base", "run_id": 1, "total_protocol_time_ms": 9.0},
            ]
        )

        result = calculate_paired_significance(
            df,
            group_key="scenario_point",
            metric="total_protocol_time_ms",
            candidate="SGCT",
            baselines=["HLCT-Base"],
        )

        self.assertEqual(1, len(result))
        self.assertGreater(result.iloc[0]["mean_improvement_pct"], 0)
        self.assertEqual(1.0, result.iloc[0]["win_rate"])

    def test_paired_significance_omits_normal_p_value_for_tiny_samples(self):
        pd = __import__("pandas")
        df = pd.DataFrame(
            [
                {"scenario_point": "random", "algorithm_name": "SGCT", "run_id": 0, "total_protocol_time_ms": 8.0},
                {"scenario_point": "random", "algorithm_name": "DRCT", "run_id": 0, "total_protocol_time_ms": 10.0},
                {"scenario_point": "random", "algorithm_name": "SGCT", "run_id": 1, "total_protocol_time_ms": 7.0},
                {"scenario_point": "random", "algorithm_name": "DRCT", "run_id": 1, "total_protocol_time_ms": 9.0},
            ]
        )

        result = calculate_paired_significance(
            df,
            group_key="scenario_point",
            metric="total_protocol_time_ms",
            candidate="SGCT",
            baselines=["DRCT"],
        )

        self.assertTrue(__import__("math").isnan(result.iloc[0]["paired_t_p_value_normal_approx"]))

    def test_paper_outputs_use_final_results_directory(self):
        self.assertEqual("results_paper_final", RESULTS_BASE_DIR)
        self.assertEqual(50, DEFAULT_RUNS_PER_POINT)
        self.assertIn("SGCT", PAPER_BASELINE_ALGORITHMS)
        self.assertNotIn("OCG-HLCT", PAPER_BASELINE_ALGORITHMS)
        self.assertNotIn("OCG-HLCT-SG", PAPER_BASELINE_ALGORITHMS)
        self.assertNotIn("OCG-HLCT-PB", PAPER_BASELINE_ALGORITHMS)
        self.assertNotIn("HLCT-Base", PAPER_BASELINE_ALGORITHMS)
        self.assertNotIn("BGCT", PAPER_BASELINE_ALGORITHMS)
        self.assertNotIn("BGCT_Random", PAPER_BASELINE_ALGORITHMS)

    def test_paper_only_selects_only_sgct_paper_experiments(self):
        selected = selected_experiments([], paper_only=True)

        self.assertEqual(FORMAL_PAPER_EXPERIMENTS, [experiment["name"] for experiment in selected])

    def test_paper_only_rejects_explicit_experiment_mix(self):
        with self.assertRaises(ValueError):
            selected_experiments(["formal_experiment10_algorithm_comparison"], paper_only=True)

    def test_experiment12_hlct_feedback_is_configured(self):
        experiments = {experiment["name"]: experiment for experiment in FORMAL_EXPERIMENTS}

        self.assertIn("formal_experiment12_hlct_feedback", experiments)
        self.assertIn("HLCT-Base(no_adaptive_cbit)", EXPERIMENT12_HLCT_LIBRARY)
        self.assertIn("HLCT-Base(no_multibit_fallback)", EXPERIMENT12_HLCT_LIBRARY)
        self.assertFalse(
            EXPERIMENT12_HLCT_LIBRARY["HLCT-Base(no_adaptive_cbit)"]["config"][
                "enable_adaptive_cbit"
            ]
        )
        self.assertFalse(
            EXPERIMENT12_HLCT_LIBRARY["HLCT-Base(no_multibit_fallback)"]["config"][
                "enable_multibit_fallback"
            ]
        )
        self.assertEqual(
            list(EXPERIMENT12_HLCT_LIBRARY.keys()),
            algorithms_for_experiment("formal_experiment12_hlct_feedback", []),
        )

    def test_prefixed_scenario_rejects_impossible_unique_id_count(self):
        with self.assertRaises(ValueError):
            generate_scenario(
                {
                    "TOTAL_TAGS": 5000,
                    "BINARY_LENGTH": 96,
                    "id_distribution": "prefixed",
                    "prefix_length": 88,
                }
            )


if __name__ == "__main__":
    unittest.main()



