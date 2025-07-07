"""Integration tests that run flow scripts."""

import subprocess
from pathlib import Path

import pytest

# Get all flow files
flows_dir = Path(__file__).parent.parent.parent / "flows"
flow_files = sorted(flows_dir.glob("*.py"))


@pytest.mark.parametrize("flow_file", flow_files, ids=[f.stem for f in flow_files])
def test_flow(flow_file):
    """Run each flow file as a subprocess test."""
    import os

    try:
        result = subprocess.run(
            ["uv", "run", str(flow_file)],
            capture_output=True,
            text=True,
            env=os.environ.copy(),  # Pass environment variables including PREFECT_API_URL
            timeout=60,  # 60 second timeout per test
        )
        assert result.returncode == 0, (
            f"Flow {flow_file.name} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    except subprocess.TimeoutExpired as e:
        pytest.fail(
            f"Flow {flow_file.name} timed out after 60 seconds:\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        )
