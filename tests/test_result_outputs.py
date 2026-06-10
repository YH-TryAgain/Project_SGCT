import csv
import unittest
from pathlib import Path


class ResultOutputPolicyTests(unittest.TestCase):
    def test_current_result_csvs_do_not_include_bgct_entries(self):
        result_roots = [root for root in [Path("results"), Path("results_paper_final")] if root.exists()]
        if not result_roots:
            self.skipTest("results directories have not been generated")

        offenders = []
        for results_root in result_roots:
            for csv_path in results_root.rglob("*.csv"):
                with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                    header = next(csv.reader(handle), [])
                bgct_columns = [column for column in header if column.startswith("BGCT")]
                bgct_rows = []
                with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                    for row_number, row in enumerate(csv.reader(handle), start=1):
                        if any(cell.startswith("BGCT") for cell in row):
                            bgct_rows.append(row_number)
                if bgct_columns or bgct_rows:
                    offenders.append((str(csv_path), bgct_columns, bgct_rows[:5]))

        self.assertEqual([], offenders)

    def test_exp4_suffix_tuning_keeps_non_bgct_baselines(self):
        csv_path = Path("results/exp4_pb_suffix_tuning/total_protocol_time_ms.csv")
        if not csv_path.exists():
            self.skipTest("Exp4 suffix tuning result has not been generated")

        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            header = next(csv.reader(handle), [])

        for algorithm_name in ["HLCT-Base", "DRCT", "EMDT", "NLHQT(n=2)"]:
            self.assertIn(algorithm_name, header)


if __name__ == "__main__":
    unittest.main()



