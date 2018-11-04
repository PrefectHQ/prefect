import os
import pytest
import subprocess

from click.testing import CliRunner

import prefect


def test_cli_is_installed():
    output = subprocess.check_output(["prefect"])
    assert b"The Prefect CLI" in output


def test_cli_picks_up_env_vars_not_in_config_file():
    env = os.environ.copy()
    env["PREFECT__DEFINITELY_NOT_REAL"] = "00"
    out = subprocess.check_output(
        ["prefect", "configure", "list_config"], stderr=subprocess.STDOUT, env=env
    )
    assert b"definitely_not_real" in out
