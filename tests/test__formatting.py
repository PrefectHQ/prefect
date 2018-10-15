import os
import pytest
import shlex
import subprocess
import sys


@pytest.mark.skipif(sys.version_info < (3, 6), reason="Black requires Python 3.6+")
def test_black_formatting():
    # make sure we're in the right place
    assert __file__.endswith("/tests/test__formatting.py")
    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    result = subprocess.call(shlex.split("black --check {}".format(prefect_dir)))
    assert result == 0, "Prefect repo did not pass Black formatting!"
