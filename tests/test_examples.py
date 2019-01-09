import os
import subprocess
from pathlib import Path

import pytest

import prefect

examples_dir = str(Path(__file__).parents[1] / "examples")


def test_examples_exist():
    assert os.path.exists(examples_dir)
    assert len(os.listdir(examples_dir)) > 0


@pytest.mark.parametrize("f", os.listdir(examples_dir))
def test_all_examples_run_without_error(f):
    subprocess.check_call(["python", os.path.join(examples_dir, f)])
