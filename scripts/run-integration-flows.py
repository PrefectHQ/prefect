#!/usr/bin/env python3
"""
Runs all Python files in the given path.

The path defaults to the `flows` directory in the repository root.

Usage:

    run-integration-flows.py [<target-directory>]

Example:

    PREFECT_API_URL="http://localhost:4200/api" ./scripts/run-integration-flows.py
"""

import subprocess
import sys
from pathlib import Path
from typing import Union

import prefect
from prefect import __version__

# See https://github.com/PrefectHQ/prefect/pull/9136
DEFAULT_PATH = prefect.__development_base_path__ / "flows"


def run_script(script_path: str):
    print(f" {script_path} ".center(90, "-"), flush=True)
    try:
        result = subprocess.run(
            ["uv", "run", script_path], capture_output=True, text=True, check=True
        )
        return result.stdout, result.stderr, None
    except subprocess.CalledProcessError as e:
        return e.stdout, e.stderr, e


def run_flows(search_path: Union[str, Path]):
    print(f"Running integration tests with client version: {__version__}")
    scripts = sorted(Path(search_path).glob("**/*.py"))
    errors = []
    for script in scripts:
        print(f"Running {script}")
        try:
            run_script(str(script))
        except Exception as e:
            print(f"Error running {script}: {e}")
            errors.append(e)

    assert not errors, "Errors occurred while running flows"


if __name__ == "__main__":
    run_flows(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
