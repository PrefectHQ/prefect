import os
import subprocess
import tempfile

import pytest
from click.testing import CliRunner

import prefect
import prefect.cli


def test_cli_is_installed():
    output = subprocess.check_output(["prefect"])
    assert b"The Prefect CLI" in output


def error_flow():
    @prefect.task
    def zero_error():
        1 / 0

    with prefect.Flow("error flow") as flow:
        zero_error()

    return flow


@pytest.mark.skip(reason="CLI not yet fully implemented")
def test_run_cli():
    flow = error_flow()
    with tempfile.NamedTemporaryFile() as tmp:
        flow.to_environment_file(tmp.name)
        result = CliRunner().invoke(prefect.cli.run, tmp.name)
    assert 'Failed("Some reference tasks failed.")' in result.output
