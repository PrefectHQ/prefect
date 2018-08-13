import subprocess

import pytest

import prefect


def test_cli_is_installed():
    output = subprocess.check_output(["prefect"])
    assert b"The Prefect CLI" in output
