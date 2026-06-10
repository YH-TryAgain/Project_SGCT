import unittest

from Framework import Tag
from DRCT_strict import DRCTAlgorithm, DRCTNode, DRCTStrictAlgorithm, modify_prestr


class DRCTStrictPaperProcessTests(unittest.TestCase):
    def run_algorithm(self, algorithm, max_steps=300):
        steps = []
        for _ in range(max_steps):
            if algorithm.is_finished():
                return steps
            steps.append(algorithm.perform_step())
        self.fail("DRCT strict did not finish within the step budget")

    def test_exposes_strict_algorithm_with_compatible_alias(self):
        self.assertIs(DRCTAlgorithm, DRCTStrictAlgorithm)

    def test_paper_modify_rules_are_exact(self):
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
        algorithm = DRCTStrictAlgorithm(tags, check_mode="epc_deterministic")

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

    def test_identical_check_fallback_sends_answer_then_rest_id_before_requeue(self):
        tags = [Tag("0000"), Tag("0010"), Tag("0100")]
        algorithm = DRCTStrictAlgorithm(tags, check_bits=0)

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

    def test_default_strict_mode_samples_random_check_values(self):
        tags = [
            Tag("0000000"),
            Tag("0000001"),
            Tag("1000000"),
            Tag("1000001"),
        ]
        algorithm = DRCTStrictAlgorithm(tags, check_seed=7)

        self.run_algorithm(algorithm)

        self.assertEqual("random", algorithm.params.check_mode)
        self.assertGreater(algorithm.metrics["drct_random_check_count"], 0)


if __name__ == "__main__":
    unittest.main()



