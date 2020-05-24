# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import os
import shlex
import subprocess
import sys

import pytest
import yaml

from prefect_server.utilities.tests import yaml_sorter


def test_python_37():
    """
    Prefect Server uses ContextVars, which are only available in Python 3.7+
    """
    assert sys.version_info >= (3, 7)


def test_black_formatting():
    # make sure we're in the right place
    assert __file__.endswith("/tests/test_formatting.py")
    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    result = subprocess.call(shlex.split("black --check {}".format(prefect_dir)))
    assert result == 0, "Repo did not pass Black formatting!"


@pytest.mark.xfail(reason="mypy checks not enforced (yet)")
def test_mypy():
    # make sure we're in the right place
    assert __file__.endswith("/tests/test_formatting.py")
    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    prefect_src_dir = os.path.join(prefect_dir, "src/")
    config_file = os.path.join(prefect_dir, "setup.cfg")
    result = subprocess.call(
        shlex.split("mypy --config-file {0} {1}".format(config_file, prefect_src_dir))
    )
    assert result == 0, "Repo did not pass mypy type checks!"


pytest.mark.skip(
    reason="Hasura now sorts metadata automatically; "
    "once confirmed this test can be removed."
)


def test_hasura_metadata_is_sorted():
    # make sure we're in the right place
    assert __file__.endswith("/tests/test_formatting.py")
    prefect_dir = os.path.dirname(os.path.dirname(__file__))
    metadata = os.path.join(prefect_dir, "services/hasura/migrations", "metadata.yaml")

    with open(metadata, "r") as f:
        data = yaml.safe_load(f)

    assert data == yaml_sorter(
        data
    ), "Hasura metadata is not sorted! Try using `prefect-server hasura format-metadata`"
