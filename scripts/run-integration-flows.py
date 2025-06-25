#!/usr/bin/env python3
"""
Runs all Python files in the given path.

The path defaults to the `flows` directory in the repository root.

Usage:

    run-integration-flows.py [<target-directory>]

Example:

    PREFECT_API_URL="http://localhost:4200/api" ./scripts/run-integration-flows.py
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Union

import prefect
from prefect import __version__

# See https://github.com/PrefectHQ/prefect/pull/9136
DEFAULT_PATH = prefect.__development_base_path__ / "flows"
SCRIPT_TIMEOUT = 60  # Maximum time for any single script


def run_script(script_path: str, timeout: int = SCRIPT_TIMEOUT):
    print(f" {script_path} ".center(90, "-"), flush=True)
    start_time = time.time()

    try:
        # Use Popen for better control over process lifecycle
        process = subprocess.Popen(
            ["uv", "run", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # Start new process group to ensure all children can be killed
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )

        try:
            stdout, stderr = process.communicate(timeout=timeout)
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, process.args, stdout, stderr
                )
            return stdout, stderr, None
        except subprocess.TimeoutExpired:
            # Kill the entire process group
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                time.sleep(0.5)  # Give processes time to clean up
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.terminate()
                time.sleep(0.5)
                process.kill()

            # Get any partial output
            stdout, stderr = process.communicate(timeout=5)

            elapsed = time.time() - start_time
            error_msg = f"Script timed out after {elapsed:.1f}s (limit: {timeout}s)"
            return stdout, stderr, TimeoutError(error_msg)

    except subprocess.CalledProcessError as e:
        return e.stdout, e.stderr, e
    except Exception as e:
        elapsed = time.time() - start_time
        return "", f"Unexpected error after {elapsed:.1f}s: {str(e)}", e


def run_flows(search_path: Union[str, Path]):
    print(f"Running integration tests with client version: {__version__}")
    scripts = sorted(Path(search_path).glob("**/*.py"))
    errors = []

    for script in scripts:
        print(f"\nRunning {script}")
        stdout, stderr, error = run_script(str(script))

        if stdout:
            print("STDOUT:", stdout)
        if stderr:
            print("STDERR:", stderr)

        if error:
            print(f"Error running {script}: {error}")
            errors.append((script, error))

    if errors:
        print("\n" + "=" * 90)
        print(f"FAILURES: {len(errors)} scripts failed:")
        for script, error in errors:
            print(f"  - {script}: {type(error).__name__}: {error}")
        print("=" * 90)

    assert not errors, f"{len(errors)} scripts failed during execution"


if __name__ == "__main__":
    run_flows(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH)
