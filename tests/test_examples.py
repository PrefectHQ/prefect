import os
from pathlib import Path

import pytest

import prefect

examples_dir = str(Path(__file__).parents[1] / "examples")


def test_examples_exist():
    assert os.path.exists(examples_dir)
    assert len(os.listdir(examples_dir)) > 0
