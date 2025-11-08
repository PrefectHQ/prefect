import math
import unittest
from prefect.utilities.quantile_normalize import quantile_normalize

class TestQuantileNormalize(unittest.TestCase):
    def test_basic_unit_range(self):
        out = quantile_normalize.fn([10, 20, 30, 40, 50], 0.0, 1.0, 0.0, 1.0)
        self.assertEqual(out, [0.0, 0.25, 0.5, 0.75, 1.0])

    def test_outlier_clipped(self):
        out = quantile_normalize.fn([0, 1, 2, 1000], 0.1, 0.9, 0.0, 1.0)
        self.assertTrue(out[-1] <= 1.0 + 1e-12)

    def test_none_nan_passthrough(self):
        out = quantile_normalize.fn([1.0, None, float("nan"), 3.0], 0.0, 1.0, 0.0, 1.0)
        self.assertIsNone(out[1])
        self.assertIsNone(out[2])
        self.assertAlmostEqual(out[0], 0.0, places=9)
        self.assertAlmostEqual(out[3], 1.0, places=9)

    def test_custom_output_range(self):
        out = quantile_normalize.fn([0.0, 5.0, 10.0], 0.0, 1.0, -1.0, 1.0)
        self.assertEqual(out, [-1.0, 0.0, 1.0])

    def test_bad_ranges_raise(self):
        with self.assertRaises(ValueError):
            quantile_normalize.fn([], 0.0, 1.0, 0.0, 1.0)
        with self.assertRaises(ValueError):
            quantile_normalize.fn([1.0, 2.0], 0.9, 0.1, 0.0, 1.0)
        with self.assertRaises(ValueError):
            quantile_normalize.fn([1.0, 2.0], 0.0, 1.0, 1.0, 1.0)

if __name__ == "__main__":
    unittest.main()
