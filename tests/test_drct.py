import unittest

from Framework import Tag
from DRCT import DRCTAlgorithm, DRCTNode, DRCTParams, modify_prestr


class DRCTPaperRuleTests(unittest.TestCase):
    def test_modify_prestr_follows_paper_rules(self):
        self.assertEqual("11", modify_prestr("1", is_r1_collision=False))
        self.assertEqual("01", modify_prestr("1", is_r1_collision=True))
        self.assertEqual("0111", modify_prestr("011", is_r1_collision=False))
        self.assertEqual("01101", modify_prestr("0111", is_r1_collision=True))

    def test_default_answer_is_two_bits(self):
        self.assertEqual(2, DRCTParams().answer_bits)

    def test_initial_query_matches_paper(self):
        algorithm = DRCTAlgorithm([Tag("0010010"), Tag("1100110")])

        self.assertEqual([DRCTNode(preStr="1", seDepth=0)], algorithm.stack)


class DRCTExecutionTests(unittest.TestCase):
    def run_algorithm(self, algorithm, max_steps=300):
        steps = []
        for _ in range(max_steps):
            if algorithm.is_finished():
                return steps
            steps.append(algorithm.perform_step())
        self.fail("DRCT did not finish within the step budget")

    def test_reproduces_paper_sample_identification(self):
        tags = [
            Tag("0010010"),
            Tag("0110001"),
            Tag("0110110"),
            Tag("1001110"),
            Tag("1010101"),
            Tag("1100110"),
        ]
        algorithm = DRCTAlgorithm(tags)

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["drct_r0_collision_count"], 0)
        self.assertGreater(algorithm.metrics["drct_r1_collision_count"], 0)
        self.assertGreater(algorithm.metrics["drct_r1_sedepth_increment_count"], 0)

    def test_check_alias_is_detected_during_rest_id_and_requeued(self):
        tags = [Tag("0000"), Tag("0010"), Tag("0100")]
        algorithm = DRCTAlgorithm(tags, check_bits=0)

        self.run_algorithm(algorithm)

        self.assertEqual({tag.id for tag in tags}, algorithm.get_results())
        self.assertGreater(algorithm.metrics["check_answer_alias_count"], 0)


if __name__ == "__main__":
    unittest.main()



