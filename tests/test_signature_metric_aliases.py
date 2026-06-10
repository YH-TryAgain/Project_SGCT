import unittest

import pandas as pd

from Tool import SimulationAnalytics


class SignatureMetricAliasTests(unittest.TestCase):
    def test_existing_signature_columns_gain_signature_aliases(self):
        analytics = SimulationAnalytics()
        df = pd.DataFrame(
            [
                {
                    "TOTAL_TAGS": 10,
                    "signature_grouping_trigger_count": 2,
                    "sparse_signature_groups": 5,
                    "signature_groups_pruned": 3,
                    "signature_marker_tag_bits": 10,
                    "signature_collision_groups": 4,
                    "signature_singleton_groups": 1,
                    "max_signature_d": 8,
                }
            ]
        )

        enriched = analytics._calculate_derived_metrics(df)

        self.assertEqual(2, enriched.loc[0, "signature_grouping_trigger_count"])
        self.assertEqual(5, enriched.loc[0, "sparse_signature_groups"])
        self.assertEqual(3, enriched.loc[0, "signature_groups_pruned"])
        self.assertEqual(10, enriched.loc[0, "signature_marker_tag_bits"])
        self.assertEqual(4, enriched.loc[0, "signature_collision_groups"])
        self.assertEqual(1, enriched.loc[0, "signature_singleton_groups"])
        self.assertEqual(8, enriched.loc[0, "max_signature_d"])


if __name__ == "__main__":
    unittest.main()



