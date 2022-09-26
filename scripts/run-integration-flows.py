#!/usr/bin/env python3
"""
Runs all Python files in `/flows`
"""
import runpy

from prefect import __root_path__

for file in (__root_path__ / "flows").glob("*.py"):
    print(f"Executing {file.relative_to(__root_path__)}...")
    runpy.run_path(file, run_name="__main__")
