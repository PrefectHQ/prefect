import os
import pytest
import subprocess
import tempfile
from click.testing import CliRunner

import prefect
import prefect.cli


def test_cli_is_installed():
    output = subprocess.check_output(["prefect"])
    assert b"The Prefect CLI" in output


def test_make_user_config():
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "test-config.toml")
        with prefect.utilities.tests.set_temporary_config({"user_config_path": path}):
            CliRunner().invoke(prefect.cli.make_user_config)
        with open(path, "r") as f:
            assert f.read().startswith("# This is a user configuration file")


def error_flow():
    @prefect.task
    def zero_error():
        1 / 0

    with prefect.Flow("error flow") as flow:
        zero_error()

    return flow


def test_run_cli():
    flow = error_flow()
    with tempfile.NamedTemporaryFile() as tmp:
        flow.to_environment_file(tmp.name)
        result = CliRunner().invoke(prefect.cli.run, tmp.name)
    assert 'Failed("Some reference tasks failed.")' in result.output
