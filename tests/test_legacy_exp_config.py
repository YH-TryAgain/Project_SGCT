import unittest

import Exp1
import Exp2
import Exp3
import Exp4
import exp5
import exp6
from algorithm_base_config import ALGORITHM_LIBRARY, ALGORITHMS_TO_TEST
from DRCT_final import DRCTFinalAlgorithm
from OCG_HLCT import OCGHLCTAlgorithm


class LegacyExperimentConfigurationTests(unittest.TestCase):
    def test_global_algorithm_set_includes_current_hlct_and_final_drct(self):
        self.assertIn("HLCT-Base", ALGORITHMS_TO_TEST)
        self.assertIn("SGCT", ALGORITHMS_TO_TEST)
        self.assertIn("DRCT", ALGORITHMS_TO_TEST)
        self.assertNotIn("OCG-HLCT", ALGORITHMS_TO_TEST)
        self.assertNotIn("OCG-HLCT-SG", ALGORITHMS_TO_TEST)
        self.assertNotIn("OCG-HLCT-PB", ALGORITHMS_TO_TEST)
        self.assertNotIn("DRCT_strict", ALGORITHMS_TO_TEST)
        self.assertNotIn("BGCT", ALGORITHMS_TO_TEST)
        self.assertNotIn("BGCT_Random", ALGORITHMS_TO_TEST)
        self.assertIs(OCGHLCTAlgorithm, ALGORITHM_LIBRARY["HLCT-Base"]["class"])
        self.assertIs(DRCTFinalAlgorithm, ALGORITHM_LIBRARY["DRCT"]["class"])
        self.assertFalse(ALGORITHM_LIBRARY["DRCT"]["config"]["paper_timing"])
        self.assertTrue(ALGORITHM_LIBRARY["DRCT"]["config"]["include_reader_cmd_base_bits"])

    def test_legacy_experiments_are_configured_for_one_run_smoke(self):
        for module in [Exp1, Exp2, Exp3, Exp4, exp5, exp6]:
            self.assertEqual(1, module.NUM_RUNS_PER_POINT)

    def test_local_algorithm_lists_include_current_hlct_and_final_drct(self):
        self.assertIn("HLCT-Base", exp5.ALGORITHMS_TO_TEST)
        self.assertIn("DRCT", exp5.ALGORITHMS_TO_TEST)
        self.assertNotIn("DRCT_strict", exp5.ALGORITHMS_TO_TEST)
        self.assertIn("HLCT-Base", Exp4.BASELINE_ALGORITHMS_TO_TEST)
        self.assertIn("DRCT", Exp4.BASELINE_ALGORITHMS_TO_TEST)
        self.assertNotIn("DRCT_strict", Exp4.BASELINE_ALGORITHMS_TO_TEST)
        self.assertNotIn("BGCT", exp5.ALGORITHMS_TO_TEST)
        self.assertFalse(any(name.startswith("BGCT") for name in Exp4.ALGORITHMS_TO_TUNE))


if __name__ == "__main__":
    unittest.main()



