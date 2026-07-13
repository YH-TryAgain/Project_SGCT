import unittest
from collections import deque

from Framework import Tag, run_simulation_with_tags
from algorithm_base_config import ALGORITHM_LIBRARY
from _sgct_small_cluster_fallback import SGCTSmallClusterFallbackAlgorithm
from SGCT import SGCTAlgorithm, SGCTNode


class SGCTAlgorithmTests(unittest.TestCase):
    def run_algorithm(self, algorithm, max_steps=300):
        steps = []
        for _ in range(max_steps):
            if algorithm.is_finished():
                return steps
            steps.append(algorithm.perform_step())
        self.fail("SGCT did not finish within the step budget")

    def test_signature_probe_uses_high_order_collision_bits(self):
        tags = [
            Tag("00000000"),
            Tag("00000011"),
            Tag("00001100"),
            Tag("00001111"),
            Tag("00110000"),
            Tag("00110011"),
            Tag("00111100"),
            Tag("00111111"),
        ]
        algorithm = SGCTAlgorithm(
            tags,
            d_target_dense=6,
            d_target_normal=4,
            signature_d_min=3,
            terminal_group_size=1,
        )

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreaterEqual(algorithm.metrics["signature_grouping_trigger_count"], 1)
        self.assertGreaterEqual(algorithm.metrics["progressive_probe_count"], 1)
        self.assertGreaterEqual(algorithm.metrics["max_signature_d"], 4)

    def test_signature_split_skips_idle_groups(self):
        tags = [
            Tag("000000000"),
            Tag("000000001"),
            Tag("000011000"),
            Tag("001100000"),
            Tag("001111000"),
        ]
        algorithm = SGCTAlgorithm(
            tags,
            d_target_dense=4,
            d_target_normal=4,
            signature_d_min=4,
            terminal_group_size=1,
        )

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["signature_groups_pruned"], 0)
        self.assertEqual(0, algorithm.metrics["idle_slots"])

    def test_non_terminal_signature_children_use_bounded_short_id_cost(self):
        tags = []
        for prefix in range(16):
            for tail_bit in "01":
                tags.append(Tag(f"{prefix:04b}{tail_bit}" + "0" * 91))
        algorithm = SGCTAlgorithm(
            tags,
            d_target_dense=4,
            d_target_normal=4,
            signature_d_min=4,
            local_short_id_min_bits=8,
        )

        steps = self.run_algorithm(algorithm)

        child_steps = [
            step
            for step in steps
            if step.operation_description
            in {
                "SGCT non-terminal signature child",
                "SGCT hash short-ID child split",
            }
        ]
        self.assertTrue(child_steps)
        self.assertLessEqual(max(step.expected_max_tag_bits for step in child_steps), 8)
        self.assertEqual(0, algorithm.metrics["hash_short_id_round_count"])
        self.assertEqual(0, algorithm.metrics["hash_short_id_split_count"])

    def test_hash_short_id_creates_real_child_groups(self):
        tags = []
        for prefix in range(8):
            for suffix in range(4):
                tags.append(Tag(f"{prefix:03b}{suffix:02b}" + "0" * 11))
        algorithm = SGCTAlgorithm(
            tags,
            d_target_dense=3,
            d_target_normal=3,
            signature_d_min=3,
            enable_hash_short_id=True,
            hash_short_id_bits=1,
            hash_short_id_max_bits=8,
            enable_small_cluster_guard=False,
        )

        self.run_algorithm(algorithm, max_steps=1000)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["hash_short_id_split_count"], 0)
        self.assertGreater(algorithm.metrics["hash_short_id_collision_groups"], 0)

    def test_low_d_singletons_are_not_identified_without_epc_verify(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = SGCTAlgorithm(tags, signature_d_min=2, d_target_dense=2)

        first_step = algorithm.perform_step()
        while first_step.operation_description != "SGCT low-d selected split fallback":
            first_step = algorithm.perform_step()

        self.assertEqual(set(), algorithm.get_results())
        self.run_algorithm(algorithm)
        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertEqual(2, algorithm.metrics["epc_verification_count"])

    def test_no_position_singleton_is_not_identified_without_epc_verify(self):
        tags = [Tag("0000")]
        algorithm = SGCTAlgorithm(tags)

        result = algorithm.perform_step()

        self.assertEqual("success_slot", result.operation_type)
        self.assertEqual({"0000"}, algorithm.get_results())
        self.assertEqual(1, algorithm.metrics["epc_verification_count"])

    def test_signature_marker_metrics_separate_tag_bits_from_non_idle_count(self):
        tags = [
            Tag("000000000"),
            Tag("000000001"),
            Tag("000011000"),
            Tag("001100000"),
            Tag("001111000"),
        ]
        algorithm = SGCTAlgorithm(
            tags,
            d_target_dense=4,
            d_target_normal=4,
            signature_d_min=4,
        )

        self.run_algorithm(algorithm)

        self.assertGreater(algorithm.metrics["signature_marker_tag_bits"], 0)
        self.assertGreater(algorithm.metrics["signature_non_idle_marker_count"], 0)
        self.assertNotEqual(
            algorithm.metrics["signature_marker_tag_bits"],
            algorithm.metrics["signature_non_idle_marker_count"],
        )

    def test_target_d_slot_cap_decrements_one_bit_at_a_time(self):
        algorithm = SGCTAlgorithm(
            [Tag(format(i, "08b")) for i in range(4)],
            d_target_dense=12,
            signature_d_max=12,
            signature_slot_cap=512,
        )

        self.assertEqual(9, algorithm._target_d_for_node(algorithm.queue[0]))

    def test_small_cluster_guard_avoids_small_batch_regression(self):
        tags = []
        for cluster in range(8):
            prefix = format(cluster, "064b")
            for suffix in range(8):
                tags.append(Tag(prefix + format(suffix, "032b")))
        guarded = SGCTAlgorithm(tags, enable_small_cluster_guard=True)
        unguarded = SGCTAlgorithm(tags)

        guarded_result = run_simulation_with_tags(tags, SGCTAlgorithm, {"enable_small_cluster_guard": True})
        legacy_result = run_simulation_with_tags(
            tags,
            SGCTSmallClusterFallbackAlgorithm,
            {},
        )

        self.assertIsNotNone(guarded.delegate)
        self.assertIsNone(unguarded.delegate)
        self.assertEqual(1, guarded.metrics["small_cluster_guard_count"])
        self.assertEqual(legacy_result["identified_tags_count"], guarded_result["identified_tags_count"])
        self.assertEqual(legacy_result["total_protocol_time_us"], guarded_result["total_protocol_time_us"])

    def test_default_pb_configuration_does_not_use_non_observable_small_cluster_guard(self):
        algorithm = SGCTAlgorithm([Tag(format(i, "096b")) for i in range(32)])

        self.assertFalse(ALGORITHM_LIBRARY["SGCT"]["config"]["enable_small_cluster_guard"])
        self.assertFalse(algorithm.params.enable_small_cluster_guard)
        self.assertIsNone(algorithm.delegate)

    def test_default_pb_configuration_keeps_hash_short_id_disabled(self):
        algorithm = SGCTAlgorithm([Tag(format(i, "096b")) for i in range(32)])

        self.assertFalse(ALGORITHM_LIBRARY["SGCT"]["config"]["enable_hash_short_id"])
        self.assertFalse(algorithm.params.enable_hash_short_id)

    def test_registered_simulation_identifies_all_tags(self):
        tags = [Tag(format(i, "096b")) for i in range(16)]

        result = run_simulation_with_tags(
            tags,
            SGCTAlgorithm,
            {
                "d_target_dense": 8,
                "d_target_normal": 6,
                "terminal_group_size": 1,
            },
        )

        self.assertEqual(16, result["identified_tags_count"])
        self.assertGreater(
            result["signature_grouping_trigger_count"] + result["suffix_signature_trigger_count"],
            0,
        )

    def test_algorithm_library_registers_sg_variant(self):
        self.assertIn("SGCT", ALGORITHM_LIBRARY)
        self.assertIs(SGCTAlgorithm, ALGORITHM_LIBRARY["SGCT"]["class"])
        self.assertIn("SGCT", ALGORITHM_LIBRARY)
        self.assertIs(SGCTAlgorithm, ALGORITHM_LIBRARY["SGCT"]["class"])

    def test_algorithm_library_uses_adaptive_suffix_signature_defaults(self):
        config = ALGORITHM_LIBRARY["SGCT"]["config"]

        self.assertTrue(config["enable_adaptive_suffix_signature"])
        self.assertEqual(12, config["suffix_signature_d_max"])
        self.assertEqual(0.35, config["suffix_signature_max_non_idle_ratio"])
        self.assertEqual(1, config["max_suffix_signature_trials_per_node"])

    def test_queue_uses_deque_for_large_experiment_efficiency(self):
        algorithm = SGCTAlgorithm([Tag("0000"), Tag("0001")])

        self.assertIsInstance(algorithm.queue, deque)

    def test_signature_d_min_blocks_low_d_signature_split(self):
        tags = [Tag("0000"), Tag("0001")]
        algorithm = SGCTAlgorithm(tags, signature_d_min=2, d_target_dense=2)

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertEqual(0, algorithm.metrics["signature_grouping_trigger_count"])
        self.assertGreater(algorithm.metrics["low_d_fallback_count"], 0)

    def test_no_signature_grouping_mode_processes_idle_groups_explicitly(self):
        tags = [
            Tag("00000000"),
            Tag("00001100"),
            Tag("00110000"),
            Tag("00111100"),
        ]
        algorithm = SGCTAlgorithm(
            tags,
            enable_signature_grouping=False,
            d_target_dense=4,
            d_target_normal=4,
            signature_d_min=4,
        )

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertEqual(0, algorithm.metrics["signature_groups_pruned"])
        self.assertGreater(algorithm.metrics["idle_slots"], 0)

    def test_suffix_signature_fast_path_reduces_prefix80_time(self):
        tags = [Tag("0" * 80 + format(i, "016b")) for i in range(64)]
        base_result = run_simulation_with_tags(
            tags,
            SGCTAlgorithm,
            {
                "enable_suffix_signature": False,
                "d_target_dense": 8,
                "d_target_normal": 6,
                "signature_slot_cap": 1024,
            },
        )
        suffix_result = run_simulation_with_tags(
            tags,
            SGCTAlgorithm,
            {
                "enable_suffix_signature": True,
                "suffix_signature_d_max": 10,
                "suffix_signature_min_tags_per_slot": 0.0,
                "signature_slot_cap": 1024,
            },
        )

        self.assertEqual(64, suffix_result["identified_tags_count"])
        self.assertGreater(suffix_result["suffix_signature_trigger_count"], 0)
        self.assertLess(
            suffix_result["total_protocol_time_us"],
            base_result["total_protocol_time_us"],
        )

    def test_suffix_signature_uses_twelve_bit_suffix_window_when_configured(self):
        tags = [Tag("0" * 80 + format(i << 4, "016b")) for i in range(256)]
        algorithm = SGCTAlgorithm(
            tags,
            suffix_signature_d_max=12,
            suffix_signature_slot_cap=4096,
            signature_slot_cap=256,
            suffix_signature_min_tags_per_slot=0.0,
        )

        self.run_algorithm(algorithm, max_steps=2000)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["suffix_signature_trigger_count"], 0)
        self.assertEqual(12, algorithm.metrics["max_signature_d"])

    def test_suffix_terminal_verification_uses_remaining_suffix_bits(self):
        tags = [Tag("0" * 80 + format(i, "016b")) for i in range(32)]
        algorithm = SGCTAlgorithm(
            tags,
            suffix_signature_d_max=12,
            suffix_signature_slot_cap=4096,
            suffix_signature_min_tags_per_slot=0.0,
        )

        steps = self.run_algorithm(algorithm, max_steps=1000)

        terminal_steps = [
            step
            for step in steps
            if step.operation_description == "SGCT terminal EPC verified"
        ]
        self.assertTrue(terminal_steps)
        self.assertLessEqual(max(step.expected_max_tag_bits for step in terminal_steps), 16)

    def test_adaptive_suffix_signature_skips_after_observed_dense_feedback(self):
        tags = [
            Tag("0" * 64 + format(slot, "012b") + format(rep, "020b"))
            for rep in range(2)
            for slot in range(4096)
        ]
        algorithm = SGCTAlgorithm(tags)
        algorithm.current_node = SGCTNode(tags=tags, depth=1, last_idle_ratio=0.0)

        self.assertFalse(algorithm._should_use_suffix_signature("0" * 64, tags))

    def test_adaptive_suffix_signature_triggers_when_suffix_window_resolves_singletons(self):
        tags = [
            Tag("0" * 64 + format(i, "032b"))
            for i in range(512)
        ]
        result = run_simulation_with_tags(tags, SGCTAlgorithm, {})
        no_suffix_result = run_simulation_with_tags(
            tags,
            SGCTAlgorithm,
            {"enable_suffix_signature": False},
        )

        self.assertEqual(512, result["identified_tags_count"])
        self.assertGreater(result["suffix_signature_trigger_count"], 0)
        self.assertLess(result["total_protocol_time_us"], no_suffix_result["total_protocol_time_us"])

    def test_adaptive_suffix_signature_triggers_on_sparse_long_prefix_collisions(self):
        tags = [
            Tag("0" * 80 + format((bucket << 12) + tail, "016b"))
            for bucket in range(16)
            for tail in range(32)
        ]
        result = run_simulation_with_tags(tags, SGCTAlgorithm, {})

        self.assertEqual(512, result["identified_tags_count"])
        self.assertGreater(result["suffix_signature_trigger_count"], 0)
        self.assertLessEqual(result["max_signature_d"], 12)


if __name__ == "__main__":
    unittest.main()



