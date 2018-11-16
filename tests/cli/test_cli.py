import os
import pytest
import subprocess

from click.testing import CliRunner

import prefect


def test_cli_is_installed():
    output = subprocess.check_output(["prefect"])
    assert b"The Prefect CLI" in output
