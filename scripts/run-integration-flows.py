#!/usr/bin/env python3
"""
Runs all Python files in `/flows`
"""
import runpy

from prefect import __root_path__


def run_flows():
    for file in (__root_path__ / "flows").glob("*.py"):
        print(f"Executing {file.relative_to(__root_path__)}...", flush=True)
        runpy.run_path(file, run_name="__main__")


if __name__ == "__main__":
    run_flows()
