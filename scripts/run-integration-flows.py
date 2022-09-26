#!/usr/bin/env python3
"""
Runs all Python files in the given path.

The path defaults to the `flows` directory in the repository root.
"""
import runpy
import sys

from prefect import __root_path__

DEFAULT_PATH = __root_path__ / "flows"


def run_flows(path):
    for file in (path).glob("*.py"):
        print(f"Executing {file.relative_to(__root_path__)}...", flush=True)
        runpy.run_path(file, run_name="__main__")


if __name__ == "__main__":
    run_flows(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
