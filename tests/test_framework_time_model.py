import unittest

from Framework import AlgorithmStepResult, CONSTANTS, calculate_time_delta


class FrameworkTimeModelTests(unittest.TestCase):
    def test_response_windows_count_each_subcycle_guard_time(self):
        result = AlgorithmStepResult(
            operation_type="collision_slot",
            reader_bits=CONSTANTS.READER_CMD_BASE_BITS,
            response_windows_bits=[4, 8, 0],
        )

        actual = calculate_time_delta(result)
        expected_reader = result.reader_bits / CONSTANTS.READER_BITS_PER_US
        expected_windows = (
            CONSTANTS.T1_US + 4 / CONSTANTS.TAG_BITS_PER_US + CONSTANTS.T2_MIN_US
            + CONSTANTS.T1_US + 8 / CONSTANTS.TAG_BITS_PER_US + CONSTANTS.T2_MIN_US
            + CONSTANTS.T1_US + 0 / CONSTANTS.TAG_BITS_PER_US + CONSTANTS.T2_MIN_US
        )

        self.assertAlmostEqual(expected_reader + expected_windows, actual)


if __name__ == "__main__":
    unittest.main()



