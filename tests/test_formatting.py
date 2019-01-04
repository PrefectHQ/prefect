import os
import pytest
import shlex
import subprocess
import sys

pytestmark = pytest.mark.formatting


@pytest.mark.skipif(sys.version_info < (3, 6), reason="Black requires Python 3.6+")
def test_black_formatting():
    # make sure we know what working directory we're in
    assert __file__.endswith("/tests/test_formatting.py")

    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    result = subprocess.call(shlex.split("black --check {}".format(prefect_dir)))
    assert result == 0, "Prefect repo did not pass Black formatting!"


@pytest.mark.skipif(sys.version_info < (3, 6), reason="mypy requires Python 3.6+")
def test_mypy():
    # make sure we know what working directory we're in
    assert __file__.endswith("/tests/test_formatting.py")

    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    prefect_src_dir = os.path.join(prefect_dir, "src/")
    config_file = os.path.join(prefect_dir, "setup.cfg")
    result = subprocess.call(
        shlex.split("mypy --config-file {0} {1}".format(config_file, prefect_src_dir))
    )
    assert result == 0, "Prefect repo did not pass mypy type checks!"
