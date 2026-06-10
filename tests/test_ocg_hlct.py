import unittest

from Framework import Tag
from OCG_HLCT import (
    LocalSplitStats,
    OCGHLCTAlgorithm,
    OCGHLCTParams,
    OCGNode,
    OCGObservation,
    select_mode,
)


class OCGHLCTModeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.params = OCGHLCTParams()
        self.obs = OCGObservation(
            kind="collision",
            tags=[Tag("0000"), Tag("0011")],
            common_prefix="0" * self.params.ovg_min_prefix_bits,
            collision_positions=[2, 3],
            k_consec=2,
        )

    def test_select_mode_uses_fallback_before_other_modes(self):
        node = OCGNode(tags=[Tag("0000"), Tag("0011")], mode_hint="FALLBACK")

        mode, arg = select_mode(node, self.obs, self.params)

        self.assertEqual("FALLBACK", mode)
        self.assertEqual({"positions": [2, 3]}, arg)

    def test_select_mode_uses_two_bit_fallback_on_no_progress(self):
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("000000"), Tag("001111")],
            common_prefix="00",
            collision_positions=[2, 3, 4],
            k_consec=3,
        )
        node = OCGNode(tags=obs.tags, no_progress_streak=self.params.H_stop)

        mode, arg = select_mode(node, obs, self.params)

        self.assertEqual("FALLBACK", mode)
        self.assertEqual({"positions": [2, 3]}, arg)

    def test_select_mode_can_disable_multibit_fallback(self):
        params = OCGHLCTParams(enable_multibit_fallback=False)
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("000000"), Tag("001111")],
            common_prefix="00",
            collision_positions=[2, 3, 4],
            k_consec=3,
        )
        node = OCGNode(tags=obs.tags, no_progress_streak=params.H_stop)

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("FALLBACK", mode)
        self.assertEqual({}, arg)

    def test_select_mode_uses_explicit_ovg_hint_before_no_progress_fallback(self):
        node = OCGNode(
            tags=[Tag("0000"), Tag("0011")],
            mode_hint="OVG",
            no_progress_streak=self.params.H_stop,
            ovg_r_h=3,
        )

        mode, arg = select_mode(node, self.obs, self.params)

        self.assertEqual("OVG", mode)
        self.assertEqual({"r_h": 3}, arg)

    def test_default_ovg_retry_budget_is_single_attempt(self):
        params = OCGHLCTParams()

        self.assertEqual(1, params.R_OVG)

    def test_select_mode_respects_disabled_ovg(self):
        params = OCGHLCTParams(enable_ovg=False)
        node = OCGNode(
            tags=[Tag("0000"), Tag("0011")],
            mode_hint="OVG",
            no_progress_streak=params.H_stop,
        )

        mode, arg = select_mode(node, self.obs, params)

        self.assertEqual("FALLBACK", mode)
        self.assertEqual({"positions": [2, 3]}, arg)

    def test_select_mode_uses_ovg_when_skew_streak_and_idle_ratio_trigger(self):
        node = OCGNode(
            tags=[Tag("0000"), Tag("0011")],
            skew_streak=self.params.H_skew,
            last_idle_ratio=self.params.rho,
        )

        mode, arg = select_mode(node, self.obs, self.params)

        self.assertEqual("OVG", mode)
        self.assertEqual({"r_h": 2}, arg)

    def test_select_mode_uses_ovg_when_prefix_stagnates(self):
        node = OCGNode(
            tags=[Tag("0000"), Tag("0011")],
            prefix_stagnation_count=self.params.prefix_stagnation_threshold,
        )

        mode, arg = select_mode(node, self.obs, self.params)

        self.assertEqual("OVG", mode)
        self.assertEqual({"r_h": 2}, arg)

    def test_select_mode_uses_ovg_when_prefix_stag_score_triggers(self):
        params = OCGHLCTParams(prefix_stag_score_threshold=2)
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("0000"), Tag("0011")],
            common_prefix="0" * params.ovg_min_prefix_bits,
            collision_positions=[2, 3],
            k_consec=2,
        )
        node = OCGNode(tags=obs.tags, prefix_stag_score=2)

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("OVG", mode)
        self.assertEqual({"r_h": 2}, arg)

    def test_select_mode_uses_ovg_when_repeated_collision_pattern_triggers(self):
        params = OCGHLCTParams(repeated_pattern_threshold=2)
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("0000"), Tag("0011")],
            common_prefix="0" * params.ovg_min_prefix_bits,
            collision_positions=[2, 3],
            k_consec=2,
        )
        node = OCGNode(tags=obs.tags, repeated_collision_pattern_count=2)

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("OVG", mode)
        self.assertEqual({"r_h": 2}, arg)

    def test_select_mode_ignores_prefix_stagnation_when_disabled(self):
        params = OCGHLCTParams(enable_prefix_stagnation=False)
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("0000"), Tag("0011")],
            common_prefix="0" * params.ovg_min_prefix_bits,
            collision_positions=[2, 3],
            k_consec=2,
        )
        node = OCGNode(
            tags=obs.tags,
            prefix_stagnation_count=params.prefix_stagnation_threshold,
        )

        mode, _ = select_mode(node, obs, params)

        self.assertEqual("CBIT", mode)

    def test_select_mode_uses_pivot_after_verification_failures(self):
        node = OCGNode(
            tags=[Tag("0000"), Tag("0011")],
            verify_fail_streak=self.params.theta_v,
        )

        mode, arg = select_mode(node, self.obs, self.params)

        self.assertEqual("PIVOT", mode)
        self.assertEqual({"pivot_len": 2, "preStr": "10"}, arg)

    def test_select_mode_prefers_cbit_for_consecutive_collision_bits(self):
        node = OCGNode(tags=[Tag("0000"), Tag("0011")])

        mode, arg = select_mode(node, self.obs, self.params)

        self.assertEqual("CBIT", mode)
        self.assertEqual({"r": 2}, arg)

    def test_select_mode_can_force_cbit_only_policy(self):
        params = OCGHLCTParams(split_policy="CBIT_ONLY")
        node = OCGNode(tags=[Tag("0000"), Tag("0101")])
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="0",
            collision_positions=[1, 3],
            k_consec=1,
        )

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("CBIT", mode)
        self.assertEqual({"r": 2}, arg)

    def test_select_mode_allows_cbit_r3_for_three_consecutive_collision_bits(self):
        node = OCGNode(tags=[Tag("000000"), Tag("001111")])
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="00",
            collision_positions=[2, 3, 4],
            k_consec=3,
        )

        mode, arg = select_mode(node, obs, self.params)

        self.assertEqual("CBIT", mode)
        self.assertEqual({"r": 3}, arg)

    def test_select_mode_allows_adaptive_cbit_r4_for_dense_collision(self):
        params = OCGHLCTParams()
        node = OCGNode(tags=[Tag("000000"), Tag("001111")], last_idle_ratio=0.0)
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="00",
            collision_positions=[2, 3, 4, 5],
            k_consec=4,
        )

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("CBIT", mode)
        self.assertEqual({"r": 4}, arg)

    def test_select_mode_caps_adaptive_cbit_when_idle_rich_or_prefix_risky(self):
        params = OCGHLCTParams()
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("000000"), Tag("001111")],
            common_prefix="00",
            collision_positions=[2, 3, 4, 5],
            k_consec=4,
        )
        idle_rich_node = OCGNode(tags=obs.tags, last_idle_ratio=0.8)
        prefix_risky_node = OCGNode(
            tags=obs.tags,
            last_idle_ratio=0.0,
            prefix_stag_score=params.prefix_stag_score_threshold,
        )

        self.assertEqual(("CBIT", {"r": 3}), select_mode(idle_rich_node, obs, params))
        self.assertEqual(("CBIT", {"r": 3}), select_mode(prefix_risky_node, obs, params))

    def test_select_mode_caps_adaptive_cbit_on_prior_skew_feedback(self):
        params = OCGHLCTParams()
        obs = OCGObservation(
            kind="collision",
            tags=[Tag("000000"), Tag("001111")],
            common_prefix="00",
            collision_positions=[2, 3, 4, 5],
            k_consec=4,
        )
        node = OCGNode(tags=obs.tags, last_idle_ratio=0.0, collision_rich_streak=1)

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("CBIT", mode)
        self.assertEqual({"r": 3}, arg)

    def test_select_mode_can_disable_adaptive_cbit_width(self):
        params = OCGHLCTParams(enable_adaptive_cbit=False)
        node = OCGNode(tags=[Tag("000000"), Tag("001111")], last_idle_ratio=0.0)
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="00",
            collision_positions=[2, 3, 4, 5],
            k_consec=4,
        )

        mode, arg = select_mode(node, obs, params)

        self.assertEqual("CBIT", mode)
        self.assertEqual({"r": 3}, arg)

    def test_adaptive_cbit_r4_metric_is_recorded(self):
        tags = [Tag("000000"), Tag("001111")]
        algorithm = OCGHLCTAlgorithm(tags)
        algorithm.current_node = OCGNode(tags=tags)
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="00",
            collision_positions=[2, 3, 4, 5],
            k_consec=4,
        )

        algorithm._plan_current_collision_node()

        self.assertEqual("EXEC_SPLIT", algorithm.current_mode)
        self.assertEqual({"r": 4}, algorithm.current_mode_arg)
        self.assertEqual(1, algorithm.metrics["adaptive_cbit_r4_count"])

    def test_select_mode_does_not_use_skew_ovg_without_minimum_prefix(self):
        node = OCGNode(
            tags=[Tag("0000"), Tag("0011")],
            skew_streak=self.params.H_skew,
            last_idle_ratio=self.params.rho,
        )
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="0",
            collision_positions=[2, 3],
            k_consec=2,
        )

        mode, _ = select_mode(node, obs, self.params)

        self.assertEqual("CBIT", mode)

    def test_select_mode_uses_lock2_for_two_nonconsecutive_collision_bits(self):
        node = OCGNode(tags=[Tag("0000"), Tag("0101")])
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="0",
            collision_positions=[1, 3],
            k_consec=1,
        )

        mode, arg = select_mode(node, obs, self.params)

        self.assertEqual("LOCK2", mode)
        self.assertEqual({"positions": [1, 3]}, arg)

    def test_select_mode_uses_lock1_for_one_collision_bit(self):
        node = OCGNode(tags=[Tag("0000"), Tag("0001")])
        obs = OCGObservation(
            kind="collision",
            tags=node.tags,
            common_prefix="000",
            collision_positions=[3],
            k_consec=1,
        )

        mode, arg = select_mode(node, obs, self.params)

        self.assertEqual("LOCK1", mode)
        self.assertEqual({"positions": [3]}, arg)


class OCGHLCTExecutionTests(unittest.TestCase):
    def run_algorithm(self, algorithm, max_steps=200):
        steps = []
        for _ in range(max_steps):
            if algorithm.is_finished():
                return steps
            steps.append(algorithm.perform_step())
        self.fail("HLCT-Base did not finish within the step budget")

    def test_identifies_all_tags_in_small_collision_tree(self):
        tags = [Tag("0000"), Tag("0001"), Tag("0010"), Tag("1010")]
        algorithm = OCGHLCTAlgorithm(tags, f_default=4, r_max=3)

        steps = self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["success_slots"], 0)
        self.assertTrue(any(step.operation_type == "collision_slot" for step in steps))

    def test_ovg_path_is_observable_and_still_identifies_all_tags(self):
        tags = [Tag("000000"), Tag("000001"), Tag("000010"), Tag("000011")]
        algorithm = OCGHLCTAlgorithm(tags, H_skew=0, rho=0.0, f_default=4, ovg_min_prefix_bits=0)

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["ovg_trigger_count"], 0)
        self.assertEqual(
            algorithm.metrics["ovg_trigger_count"],
            algorithm.metrics["hbmt_ovg_trigger_count"],
        )

    def test_inspect_collision_uses_bounded_window_cost(self):
        tags = [Tag("00000000"), Tag("00000001"), Tag("00000010")]
        algorithm = OCGHLCTAlgorithm(tags, inspect_window_bits=2)
        obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="00",
            collision_positions=[6, 7],
            k_consec=2,
        )

        result = algorithm._inspect_cost(obs)

        self.assertEqual(2, result.expected_max_tag_bits)
        self.assertEqual(6, result.tag_bits)

    def test_ovg_hint_skips_collision_inspect_cost(self):
        tags = [Tag("00000000"), Tag("00000001"), Tag("00000010")]
        algorithm = OCGHLCTAlgorithm(tags)
        algorithm.queue = [OCGNode(tags=tags, mode_hint="OVG")]

        result = algorithm.perform_step()

        self.assertEqual("internal_op", result.operation_type)
        self.assertEqual("EXEC_SPLIT", algorithm.current_mode)
        self.assertEqual("OVG", algorithm.current_stats.mode)
        self.assertEqual(0, result.tag_bits)

    def test_ovg_collision_child_rehashes_before_fallback(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = OCGHLCTAlgorithm(tags, R_OVG=3, H_stop=1)
        algorithm.current_node = OCGNode(tags=tags, mode_hint="OVG", ovg_retry=0, ovg_r_h=2)
        algorithm.current_stats = LocalSplitStats(
            mode="OVG",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1

        algorithm._enqueue_child(tags, verify_failed=False)

        child = algorithm.queue[-1]
        self.assertEqual("OVG", child.mode_hint)
        self.assertEqual(1, child.ovg_retry)
        self.assertNotEqual("FALLBACK", child.mode_hint)

    def test_prefix_stagnation_promotes_child_to_ovg(self):
        tags = [Tag("0" * 20 + "00"), Tag("0" * 20 + "11")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            enable_prefix_stagnation=True,
            prefix_stagnation_threshold=2,
            ovg_min_prefix_bits=16,
            H_stop=10,
        )
        algorithm.current_node = OCGNode(tags=tags, prefix_stagnation_count=1)
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )
        algorithm.current_stats = LocalSplitStats(
            mode="CBIT",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1
        cached_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )

        algorithm._enqueue_child(tags, verify_failed=False, cached_obs=cached_obs)

        child = algorithm.queue[-1]
        self.assertEqual(2, child.prefix_stagnation_count)
        self.assertEqual("OVG", child.mode_hint)
        self.assertEqual(1, algorithm.metrics["prefix_stagnation_trigger_count"])

    def test_prefix_stag_score_accumulates_multiple_observable_signals(self):
        tags = [Tag("0" * 20 + "00"), Tag("0" * 20 + "11")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            prefix_stag_score_threshold=2,
            ovg_min_prefix_bits=16,
            H_stop=10,
        )
        algorithm.current_node = OCGNode(tags=tags, prefix_stag_score=0)
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )
        algorithm.current_stats = LocalSplitStats(
            mode="CBIT",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1
        cached_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )

        algorithm._enqueue_child(tags, verify_failed=False, cached_obs=cached_obs)

        child = algorithm.queue[-1]
        self.assertGreaterEqual(child.prefix_stag_score, 2)
        self.assertEqual("OVG", child.mode_hint)
        self.assertEqual(1, algorithm.metrics["prefix_stag_score_trigger_count"])

    def test_repeated_collision_pattern_promotes_child_to_ovg(self):
        tags = [Tag("0" * 20 + "00"), Tag("0" * 20 + "11")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            repeated_pattern_threshold=2,
            ovg_min_prefix_bits=16,
            H_stop=10,
        )
        algorithm.current_node = OCGNode(
            tags=tags,
            last_collision_signature=(20, 2, 1, 3),
            repeated_collision_pattern_count=1,
        )
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )
        algorithm.current_stats = LocalSplitStats(
            mode="CBIT",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1
        cached_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )

        algorithm._enqueue_child(tags, verify_failed=False, cached_obs=cached_obs)

        child = algorithm.queue[-1]
        self.assertEqual(2, child.repeated_collision_pattern_count)
        self.assertEqual("OVG", child.mode_hint)
        self.assertEqual(1, algorithm.metrics["repeated_pattern_trigger_count"])

    def test_disabled_prefix_stagnation_does_not_promote_child(self):
        tags = [Tag("0" * 20 + "00"), Tag("0" * 20 + "11")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            enable_prefix_stagnation=False,
            prefix_stagnation_threshold=2,
            ovg_min_prefix_bits=16,
            H_stop=10,
        )
        algorithm.current_node = OCGNode(tags=tags, prefix_stagnation_count=1)
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )
        algorithm.current_stats = LocalSplitStats(
            mode="CBIT",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1
        cached_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )

        algorithm._enqueue_child(tags, verify_failed=False, cached_obs=cached_obs)

        child = algorithm.queue[-1]
        self.assertEqual(0, child.prefix_stagnation_count)
        self.assertNotEqual("OVG", child.mode_hint)

    def test_ovg_collision_rich_child_increases_width_and_continues_ovg(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = OCGHLCTAlgorithm(tags, R_OVG=3, H_stop=10)
        algorithm.current_node = OCGNode(tags=tags, mode_hint="OVG", ovg_retry=0, ovg_r_h=2)
        algorithm.current_stats = LocalSplitStats(
            mode="OVG",
            total_groups=4,
            idle_groups=0,
            non_idle_groups=4,
            collision_child_count=2,
        )
        algorithm.group_cursor = 1

        algorithm._enqueue_child(tags, verify_failed=False)

        child = algorithm.queue[-1]
        self.assertEqual("OVG", child.mode_hint)
        self.assertEqual(3, child.ovg_r_h)
        self.assertEqual(1, algorithm.metrics["ovg_width_up_count"])

    def test_ovg_idle_rich_child_decreases_width_and_continues_ovg(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = OCGHLCTAlgorithm(tags, R_OVG=3, H_stop=10)
        algorithm.current_node = OCGNode(tags=tags, mode_hint="OVG", ovg_retry=0, ovg_r_h=2)
        algorithm.current_stats = LocalSplitStats(
            mode="OVG",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1

        algorithm._enqueue_child(tags, verify_failed=False)

        child = algorithm.queue[-1]
        self.assertEqual("OVG", child.mode_hint)
        self.assertEqual(1, child.ovg_r_h)
        self.assertEqual(1, algorithm.metrics["ovg_width_down_count"])

    def test_skewed_split_marks_collision_child_for_explicit_ovg(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = OCGHLCTAlgorithm(tags, H_stop=10)
        algorithm.current_node = OCGNode(tags=tags)
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK2",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
        )
        algorithm.group_cursor = 1
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * algorithm.params.ovg_min_prefix_bits,
            collision_positions=[algorithm.params.ovg_min_prefix_bits],
            k_consec=1,
        )

        algorithm._enqueue_child(tags, verify_failed=False)
        algorithm.current_stats.collision_child_count = 1
        algorithm._promote_unique_skew_child()

        self.assertEqual("OVG", algorithm.queue[-1].mode_hint)

    def test_disabled_ovg_does_not_promote_skewed_child(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = OCGHLCTAlgorithm(tags, enable_ovg=False, H_stop=10)
        algorithm.current_node = OCGNode(tags=tags)
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK2",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * algorithm.params.ovg_min_prefix_bits,
            collision_positions=[algorithm.params.ovg_min_prefix_bits],
            k_consec=1,
        )

        algorithm._enqueue_child(tags, verify_failed=False)
        algorithm._promote_unique_skew_child()

        self.assertNotEqual("OVG", algorithm.queue[-1].mode_hint)

    def test_false_check_singleton_is_verified_and_rolled_back(self):
        tags = [Tag("0000"), Tag("0010"), Tag("0100")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            f_default=0,
            theta_v=0,
            H_stop=1,
            fallback_after_verify_fail=True,
        )

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["epc_verification_count"], 0)
        self.assertGreater(algorithm.metrics["verify_fail_count"], 0)
        self.assertGreater(algorithm.metrics["fallback_invocation_count"], 0)

    def test_no_check_gating_child_sends_direct_epc_instead_of_short_check(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = OCGHLCTAlgorithm(tags, enable_check_gating=False)
        algorithm.current_node = OCGNode(tags=tags)
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK1",
            total_groups=2,
            idle_groups=0,
            non_idle_groups=2,
        )
        algorithm.group_cursor = 1

        result = algorithm._classify_check_group(tags, reader_bits=0)

        self.assertEqual("collision_slot", result.operation_type)
        self.assertEqual(8, result.tag_bits)
        self.assertEqual(4, result.expected_max_tag_bits)

    def test_fused_check_window_caches_collision_observation_for_child(self):
        tags = [Tag("000000"), Tag("000011")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            enable_fused_check_window=True,
            fused_window_bits=2,
        )
        algorithm.current_node = OCGNode(tags=tags)
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK1",
            total_groups=2,
            idle_groups=0,
            non_idle_groups=2,
        )
        algorithm.group_cursor = 1

        result = algorithm._classify_check_group(tags, reader_bits=0)

        self.assertEqual("collision_slot", result.operation_type)
        self.assertEqual(12, result.tag_bits)
        self.assertEqual(6, result.expected_max_tag_bits)
        self.assertTrue(algorithm.queue[-1].has_cached_window)
        self.assertEqual([4, 5], algorithm.queue[-1].cached_collision_positions)

    def test_cached_fused_window_skips_next_inspect_cost(self):
        tags = [Tag("000000"), Tag("000011")]
        cached = OCGNode(
            tags=tags,
            has_cached_window=True,
            cached_common_prefix="0000",
            cached_collision_positions=[4, 5],
            cached_k_consec=2,
        )
        algorithm = OCGHLCTAlgorithm(tags)
        algorithm.queue = [cached]

        result = algorithm.perform_step()

        self.assertEqual("internal_op", result.operation_type)
        self.assertEqual(0, result.tag_bits)
        self.assertEqual("EXEC_SPLIT", algorithm.current_mode)
        self.assertEqual(1, algorithm.metrics["fcw_cache_hit_count"])

    def test_fused_check_window_records_cache_creation_metric(self):
        tags = [Tag("000000"), Tag("000011")]
        algorithm = OCGHLCTAlgorithm(tags, fused_window_bits=2)
        algorithm.current_node = OCGNode(tags=tags)
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK1",
            total_groups=2,
            idle_groups=0,
            non_idle_groups=2,
        )
        algorithm.group_cursor = 1

        algorithm._classify_check_group(tags, reader_bits=0)

        self.assertEqual(1, algorithm.metrics["fcw_cache_created_count"])

    def test_adaptive_fcw_uses_wider_window_on_ovg_recovery(self):
        tags = [Tag("00000000"), Tag("00001111")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            fused_window_bits=4,
            adaptive_fused_window_bits=6,
            enable_adaptive_fcw=True,
        )
        algorithm.current_node = OCGNode(tags=tags, mode_hint="OVG")
        algorithm.current_stats = LocalSplitStats(
            mode="OVG",
            total_groups=4,
            idle_groups=2,
            non_idle_groups=2,
        )
        algorithm.group_cursor = 1

        result = algorithm._classify_check_group(tags, reader_bits=0)

        self.assertEqual(20, result.tag_bits)
        self.assertEqual(10, result.expected_max_tag_bits)

    def test_adaptive_fcw_fast_path_keeps_base_window_without_risk_signals(self):
        tags = [Tag("000000"), Tag("000011")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            enable_adaptive_fcw=True,
            fused_window_bits=4,
            adaptive_fused_window_bits=12,
        )
        algorithm.current_node = OCGNode(tags=tags, fcw_bits=12)
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK1",
            total_groups=2,
            idle_groups=0,
            non_idle_groups=2,
        )

        self.assertEqual(4, algorithm._effective_fused_window_bits())

    def test_adaptive_fcw_increases_child_window_on_prefix_stag_score(self):
        tags = [Tag("0" * 20 + "00"), Tag("0" * 20 + "11")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            enable_adaptive_fcw=True,
            fused_window_bits=4,
            adaptive_fcw_max_bits=16,
            ovg_min_prefix_bits=16,
            H_stop=10,
        )
        algorithm.current_node = OCGNode(tags=tags, fcw_bits=4)
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )
        algorithm.current_stats = LocalSplitStats(
            mode="CBIT",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1
        cached_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0" * 20,
            collision_positions=[20, 21],
            k_consec=2,
        )

        algorithm._enqueue_child(tags, verify_failed=False, cached_obs=cached_obs)

        child = algorithm.queue[-1]
        self.assertEqual(8, child.fcw_bits)
        self.assertEqual(1, algorithm.metrics["fcw_width_up_count"])

    def test_adaptive_fcw_decreases_child_window_on_idle_rich_split(self):
        tags = [Tag("0" * 20 + "00"), Tag("0" * 20 + "11")]
        algorithm = OCGHLCTAlgorithm(
            tags,
            enable_adaptive_fcw=True,
            fused_window_bits=4,
            adaptive_fcw_min_bits=2,
            H_stop=10,
        )
        algorithm.current_node = OCGNode(tags=tags, fcw_bits=8)
        algorithm.current_obs = OCGObservation(
            kind="collision",
            tags=tags,
            common_prefix="0",
            collision_positions=[1, 2],
            k_consec=2,
        )
        algorithm.current_stats = LocalSplitStats(
            mode="LOCK2",
            total_groups=4,
            idle_groups=3,
            non_idle_groups=1,
            collision_child_count=1,
        )
        algorithm.group_cursor = 1

        algorithm._enqueue_child(tags, verify_failed=False)

        child = algorithm.queue[-1]
        self.assertEqual(4, child.fcw_bits)
        self.assertEqual(1, algorithm.metrics["fcw_width_down_count"])

    def test_finalize_metrics_reports_fcw_cache_hit_ratio(self):
        tags = [Tag("000000"), Tag("000011")]
        algorithm = OCGHLCTAlgorithm(tags)
        algorithm.metrics["fcw_cache_created_count"] = 4
        algorithm.metrics["fcw_cache_hit_count"] = 3

        algorithm._finalize_metrics()

        self.assertEqual(0.75, algorithm.metrics["fcw_cache_hit_ratio"])


if __name__ == "__main__":
    unittest.main()



