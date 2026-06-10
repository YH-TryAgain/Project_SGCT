import random
import unittest

from Framework import run_simulation
from algorithm_base_config import ALGORITHM_LIBRARY
from ICT import ICT_Algorithm


class RegisteredAlgorithmSmokeTests(unittest.TestCase):
    def run_registered_algorithm(self, name, scenario):
        random.seed(12345)
        info = ALGORITHM_LIBRARY[name]
        config = dict(info.get("config", {}))
        config.update({"ber": 0.0, "enable_resource_monitoring": True})
        return run_simulation(scenario, info["class"], config)

    def test_nlhqt_finishes_on_sequential_ids(self):
        scenario = {
            "TOTAL_TAGS": 16,
            "BINARY_LENGTH": 16,
            "id_distribution": "sequential",
        }

        result = self.run_registered_algorithm("NLHQT(n=2)", scenario)

        self.assertEqual(16, result["identified_tags_count"])

    def test_nlhqt_n1_finishes_on_sequential_ids(self):
        scenario = {
            "TOTAL_TAGS": 16,
            "BINARY_LENGTH": 16,
            "id_distribution": "sequential",
        }

        result = self.run_registered_algorithm("NLHQT(n=1)", scenario)

        self.assertEqual(16, result["identified_tags_count"])

    def test_nlhqt_finishes_on_prefixed_ids(self):
        scenario = {
            "TOTAL_TAGS": 16,
            "BINARY_LENGTH": 16,
            "id_distribution": "prefixed",
            "prefix_length": 8,
        }

        result = self.run_registered_algorithm("NLHQT(n=2)", scenario)

        self.assertEqual(16, result["identified_tags_count"])

    def test_nlhqt_finishes_when_short_id_tail_is_smaller_than_n_way(self):
        scenario = {
            "TOTAL_TAGS": 32,
            "BINARY_LENGTH": 32,
            "id_distribution": "dispersed",
        }

        result = self.run_registered_algorithm("NLHQT(n=2)", scenario)

        self.assertEqual(32, result["identified_tags_count"])

    def test_ict_finishes_on_random_ids(self):
        scenario = {
            "TOTAL_TAGS": 16,
            "BINARY_LENGTH": 16,
            "id_distribution": "random",
        }
        result = run_simulation(scenario, ICT_Algorithm, {"ber": 0.0})

        self.assertEqual(16, result["identified_tags_count"])

    def test_extended_registered_algorithms_finish_on_random_ids(self):
        scenario = {
            "TOTAL_TAGS": 12,
            "BINARY_LENGTH": 16,
            "id_distribution": "random",
        }

        for name in ["ICT", "SD-CGQT", "SUBF-CGDFSA"]:
            with self.subTest(name=name):
                result = self.run_registered_algorithm(name, scenario)
                self.assertEqual(12, result["identified_tags_count"])

    def test_bgct_family_is_not_registered(self):
        self.assertNotIn("BGCT", ALGORITHM_LIBRARY)
        self.assertNotIn("BGCT_Random", ALGORITHM_LIBRARY)


if __name__ == "__main__":
    unittest.main()



