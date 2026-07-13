import unittest

from Framework import Tag, run_simulation_with_tags
from DRCT import (
    DRCTAlgorithm,
    DRCTNode,
    DRCTParams,
    modify_prestr,
)


class DRCTPaperRulesTests(unittest.TestCase):
    def run_algorithm(self, algorithm, max_steps=400):
        steps = []
        for _ in range(max_steps):
            if algorithm.is_finished():
                return steps
            steps.append(algorithm.perform_step())
        self.fail("DRCT final did not finish within the step budget")

    def test_paper_constants_and_modify_rules(self):
        params = DRCTParams()

        self.assertEqual(4, params.check_bits)
        self.assertEqual(2, params.answer_bits)
        self.assertEqual(40000, params.data_rate_bps)
        self.assertEqual(25.0, params.t1_us)
        self.assertEqual(25.0, params.t2_us)
        self.assertFalse(params.paper_timing)
        self.assertTrue(params.include_reader_cmd_base_bits)
        self.assertEqual("11", modify_prestr("1", is_r1_collision=False))
        self.assertEqual("01", modify_prestr("1", is_r1_collision=True))
        self.assertEqual("0111", modify_prestr("011", is_r1_collision=False))
        self.assertEqual("01101", modify_prestr("0111", is_r1_collision=True))

    def test_reproduces_paper_sample_query_order_and_depth_updates(self):
        tags = [
            Tag("0010010"),
            Tag("0110001"),
            Tag("0110110"),
            Tag("1001110"),
            Tag("1010101"),
            Tag("1100110"),
        ]
        algorithm = DRCTAlgorithm(tags, check_mode="epc_deterministic")

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertEqual(
            [
                DRCTNode(preStr="1", seDepth=0),
                DRCTNode(preStr="01", seDepth=1),
                DRCTNode(preStr="011", seDepth=1),
                DRCTNode(preStr="0111", seDepth=1),
                DRCTNode(preStr="01101", seDepth=2),
                DRCTNode(preStr="11", seDepth=0),
                DRCTNode(preStr="101", seDepth=1),
            ],
            algorithm.query_history,
        )
        self.assertEqual(7, algorithm.metrics["drct_r1_sedepth_increment_count"])
        self.assertEqual(0, algorithm.metrics["drct_unresolved_stack_empty_count"])

    def test_identical_check_fallback_answers_then_rest_id_detects_collision(self):
        tags = [Tag("0000"), Tag("0010"), Tag("0100")]
        algorithm = DRCTAlgorithm(tags, check_bits=0)

        steps = self.run_algorithm(algorithm)

        fallback_steps = [
            step
            for step in steps
            if "fallback collision after identical Check" in step.operation_description
        ]
        self.assertTrue(fallback_steps)
        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["check_answer_alias_count"], 0)
        self.assertGreaterEqual(fallback_steps[0].reader_bits, algorithm.params.answer_bits)
        self.assertGreater(fallback_steps[0].tag_bits, 0)

    def test_default_mode_samples_random_check_values(self):
        tags = [
            Tag("0000000"),
            Tag("0000001"),
            Tag("1000000"),
            Tag("1000001"),
        ]
        algorithm = DRCTAlgorithm(tags, check_seed=7)

        self.run_algorithm(algorithm)

        self.assertEqual("random", algorithm.params.check_mode)
        self.assertGreater(algorithm.metrics["drct_random_check_count"], 0)

    def test_framework_simulation_identifies_all_tags_and_reports_drct_metrics(self):
        tags = [
            Tag("0010010"),
            Tag("0110001"),
            Tag("0110110"),
            Tag("1001110"),
            Tag("1010101"),
            Tag("1100110"),
        ]

        result = run_simulation_with_tags(
            tags,
            DRCTAlgorithm,
            {"check_mode": "epc_deterministic", "enable_resource_monitoring": True},
        )

        self.assertEqual(len(tags), result["identified_tags_count"])
        self.assertGreater(result["drct_query_count"], 0)
        self.assertGreater(result["drct_r0_collision_count"], 0)
        self.assertGreater(result["drct_r1_collision_count"], 0)
        self.assertIn("channel_use_ratio", result)
        self.assertAlmostEqual(
            (result["success_slots"] + result["collision_slots"])
            / (result["success_slots"] + result["collision_slots"] + result["idle_slots"]),
            result["channel_use_ratio"],
        )
        self.assertEqual(2, result["peak_metrics"]["stack_depth"])

    def test_unified_timing_is_used_by_default(self):
        tags = [Tag("0"), Tag("1")]
        result = run_simulation_with_tags(
            tags,
            DRCTAlgorithm,
            {"check_mode": "epc_deterministic", "enable_resource_monitoring": True},
        )

        self.assertEqual(2, result["identified_tags_count"])
        self.assertEqual(1, result["drct_query_count"])
        self.assertEqual(0, result["collision_slots"])
        self.assertEqual(0, result["idle_slots"])
        self.assertEqual(2, result["success_slots"])
        self.assertEqual(1.0, result["channel_use_ratio"])
        self.assertEqual(22 + 2 + 2 * 2, result["total_reader_bits"])
        self.assertEqual(2 * 4, result["total_tag_bits"])
        self.assertNotAlmostEqual(450.0, result["total_protocol_time_us"])

    def test_paper_timing_can_still_be_enabled_for_reference_checks(self):
        tags = [Tag("0"), Tag("1")]
        result = run_simulation_with_tags(
            tags,
            DRCTAlgorithm,
            {
                "check_mode": "epc_deterministic",
                "enable_resource_monitoring": True,
                "paper_timing": True,
                "include_reader_cmd_base_bits": False,
            },
        )

        self.assertEqual(2 + 2 * 2, result["total_reader_bits"])
        self.assertEqual(2 * 4, result["total_tag_bits"])
        self.assertAlmostEqual(450.0, result["total_protocol_time_us"])


if __name__ == "__main__":
    unittest.main()
