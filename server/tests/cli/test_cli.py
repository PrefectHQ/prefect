# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import os
import subprocess
import tempfile

import pytest
from click.testing import CliRunner

import prefect_server
import prefect_server.cli


def test_cli_is_installed():
    output = subprocess.check_output(["prefect-server"])
    assert b"The Prefect Server CLI" in output


def test_make_user_config():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "test-config.toml")
        with prefect_server.utilities.tests.set_temporary_config(
            "user_config_path", path
        ):
            CliRunner().invoke(prefect_server.cli.make_user_config)
        with open(path, "r") as f:
            assert f.read().startswith("# This is a user configuration file")
