import os
import subprocess

import prefect


def test_prefect_version_is_updated_everywhere():
    """
    Tests that prefect.__version__ matches the version defined in setup.py
    """
    current_version = prefect.__version__

    cwd = os.path.dirname(os.path.dirname(__file__))
    cmd = ["python", "setup.py", "--version"]
    setup_version = subprocess.check_output(cmd, cwd=cwd).strip().decode()

    assert setup_version == current_version
