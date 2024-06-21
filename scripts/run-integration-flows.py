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
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Union

import prefect
from prefect import __version__

# See https://github.com/PrefectHQ/prefect/pull/9136
DEFAULT_PATH = prefect.__development_base_path__ / "flows"


def run_script(script_path: str):
    print(f" {script_path} ".center(90, "-"), flush=True)
    result = subprocess.run(["python", script_path], capture_output=True, text=True)
    return result.stdout, result.stderr


def run_flows(search_path: Union[str, Path]):
    count = 0
    print(f"Running integration tests with client version: {__version__}")
    scripts = sorted(Path(search_path).glob("**/*.py"))
    with ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run_script, scripts))

    for script, (stdout, stderr) in zip(scripts, results):
        print(f" {script.relative_to(search_path)} ".center(90, "-"), flush=True)
        print(stdout)
        print(stderr)
        print("".center(90, "-") + "\n", flush=True)
        count += 1


if __name__ == "__main__":
    run_flows(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
