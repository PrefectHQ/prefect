import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src')) # fix import path
import unittest
import math
from pydantic import BaseModel
from typing import List
from log_transform import log_transform, LogTransformation

class TestLogTransform(unittest.TestCase):
    def test_empty_data(self):  # making sure empty input results in empty list
        data = []
        config = LogTransformation()
        result = log_transform(data, config)
        self.assertEqual(result, [])
    
    def test_basic_log_transform(self):  # testing some values with base 10
        data = [1, 10, 100]
        config = LogTransformation(base=10, offset=0)
        result = log_transform(data, config)
        answers = [0.0, 1.0, 2.0]
        self.assertEqual(result, answers)

    def test_invalid_values(self):  # handling errors
        data = [-2]
        config = LogTransformation(offset=1)  # -2+1 = -1
        with self.assertRaises(ValueError):  # log(-1) is invalid
            log_transform(data, config)


if __name__ == '__main__':
    unittest.main()  # run tests