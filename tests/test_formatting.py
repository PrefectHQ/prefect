import os
import shlex
import subprocess


def test_black_formatting():
    # make sure we're in the right place
    assert __file__.endswith("/tests/test_formatting.py")
    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    result = subprocess.call(shlex.split("black --check {}".format(prefect_dir)))
    assert result == 0, "Prefect repo did not pass Black formatting!"
