#!/usr/bin/env python3
"""
Runs all Python files in the given path.

The path defaults to the `flows` directory in the repository root.

Usage:

    run-integration-flows.py [<target-directory>]

Example:

    PREFECT_API_URL="http://localhost:4200" ./scripts/run-integration-flows.py
"""
import os
import runpy
import sys
from pathlib import Path
from typing import Union

import prefect
from prefect import __version__

# See https://github.com/PrefectHQ/prefect/pull/9136
DEFAULT_PATH = (
    getattr(
        prefect, "__development_base_path__", getattr(prefect, "__root_path__", None)
    )
    / "flows"
)


def run_flows(search_path: Union[str, Path]):
    count = 0
    print(f"Running integration tests with client version: {__version__}")
    server_version = os.environ.get("TEST_SERVER_VERSION")
    if server_version:
        print(f"and server version: {server_version}")

    for file in sorted(Path(search_path).glob("*.py")):
        print(f" {file.relative_to(search_path)} ".center(90, "-"), flush=True)
        runpy.run_path(file, run_name="__main__")
        print("".center(90, "-") + "\n", flush=True)
        count += 1

    if not count:
        print(f"No Python files found at {search_path}")
        exit(1)


if __name__ == "__main__":
    run_flows(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
