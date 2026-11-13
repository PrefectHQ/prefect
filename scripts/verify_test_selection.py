"""Verify that every test file under tests/ is selected by the CI workflow.

This script parses .github/workflows/python-tests.yaml, discovers all
test files on disk, and checks that every file is covered by both the
`PYTEST_SELECTION` of the regular test jobs and the Logfire profiling
test types. It exits non-zero if any test file would be silently skipped.
"""

from __future__ import annotations

import fnmatch
import os
import sys
from typing import Any

import yaml

WORKFLOW_PATH = ".github/workflows/python-tests.yaml"

# Jobs whose test step runs `pytest $PYTEST_SELECTION`.
REGULAR_TEST_JOBS = ("run-tests", "run-canonical-tests")
LOGFIRE_PROFILE_JOB = "profile-tests-with-logfire"

# Test directories that are handled by dedicated jobs and should not be
# flagged as uncovered.
SEPARATELY_HANDLED = {
    "tests/typesafety",
}


def discover_test_files(root: str = "tests") -> set[str]:
    """Find all test_*.py and *_test.py files under *root*."""
    test_files: set[str] = set()
    for dirpath, _dirnames, filenames in os.walk(root):
        for f in filenames:
            if (f.startswith("test_") or f.endswith("_test.py")) and f.endswith(".py"):
                path = os.path.join(dirpath, f).replace("\\", "/")
                test_files.add(path)
    return test_files


def parse_modules(modules_str: str) -> tuple[list[str], list[str], list[str]]:
    """Split a modules string into (paths, ignores, ignore_globs)."""
    parts = modules_str.split()
    paths: list[str] = []
    ignores: list[str] = []
    ignore_globs: list[str] = []

    for part in parts:
        if part.startswith("--ignore="):
            ignores.append(part[len("--ignore=") :])
        elif part.startswith("--ignore-glob="):
            pattern = part[len("--ignore-glob=") :]
            ignore_globs.append(pattern.strip("\"'"))
        elif not part.startswith("-"):
            paths.append(part)

    return paths, ignores, ignore_globs


def file_covered_by(
    filepath: str,
    paths: list[str],
    ignores: list[str],
    ignore_globs: list[str],
) -> bool:
    """Return True if *filepath* would be collected by an entry."""
    # Must be under at least one of the specified paths
    matched = False
    for p in paths:
        p_norm = p.rstrip("/")
        if filepath == p_norm or filepath.startswith(p_norm + "/"):
            matched = True
            break
    if not matched:
        return False

    # Must not be excluded by --ignore
    for ign in ignores:
        ign_norm = ign.rstrip("/")
        if filepath == ign_norm or filepath.startswith(ign_norm + "/"):
            return False

    # Must not be excluded by --ignore-glob
    for pattern in ignore_globs:
        if fnmatch.fnmatch(filepath, pattern):
            return False

    return True


def regular_test_selections(jobs: dict[str, Any]) -> list[str]:
    """Return the `PYTEST_SELECTION` consumed by each regular test job."""
    selections: list[str] = []
    for job_name in REGULAR_TEST_JOBS:
        steps = [
            step
            for step in jobs[job_name]["steps"]
            if "PYTEST_SELECTION" in step.get("env", {})
        ]
        if len(steps) != 1 or "$PYTEST_SELECTION" not in steps[0].get("run", ""):
            raise ValueError(
                f"{job_name} must have exactly one step that runs "
                "`pytest $PYTEST_SELECTION`"
            )
        selections.append(steps[0]["env"]["PYTEST_SELECTION"])
    return selections


def uncovered_test_files(relevant: set[str], selections: list[str]) -> list[str]:
    covered: set[str] = set()
    for selection in selections:
        paths, ignores, ignore_globs = parse_modules(selection)
        for f in relevant:
            if file_covered_by(f, paths, ignores, ignore_globs):
                covered.add(f)
    return sorted(relevant - covered)


def main() -> None:
    with open(WORKFLOW_PATH) as f:
        jobs = yaml.safe_load(f)["jobs"]

    all_test_files = discover_test_files("tests")

    # Remove files under separately-handled directories
    relevant = {
        f
        for f in all_test_files
        if not any(f == sh or f.startswith(sh + "/") for sh in SEPARATELY_HANDLED)
    }

    scopes = {
        "regular test job PYTEST_SELECTION": regular_test_selections(jobs),
        f"{LOGFIRE_PROFILE_JOB} test-type": [
            entry["modules"]
            for entry in jobs[LOGFIRE_PROFILE_JOB]["strategy"]["matrix"]["test-type"]
        ],
    }

    failed = False
    for scope, selections in scopes.items():
        uncovered = uncovered_test_files(relevant, selections)
        if uncovered:
            failed = True
            print(f"ERROR: The following test files are not covered by any {scope}:")
            for f in uncovered:
                print(f"  {f}")
            print(f"\nTotal uncovered: {len(uncovered)}")
        else:
            print(f"OK: All {len(relevant)} test files are covered by the {scope}.")

    if failed:
        print(f"\nPlease update the test selection in {WORKFLOW_PATH}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
