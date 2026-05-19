"""Verify that every test file under tests/ is covered by at least one
test matrix entry in the CI workflow.

This script parses .github/workflows/python-tests.yaml, discovers all
test files on disk, and checks that the union of the run-tests matrix
entries covers every file. It exits non-zero if any test file would be
silently skipped by CI.
"""

from __future__ import annotations

import fnmatch
import os
import sys

import yaml

WORKFLOW_PATH = ".github/workflows/python-tests.yaml"

# Test directories that are handled by dedicated jobs outside the
# run-tests matrix and should not be flagged as uncovered.
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


def validate_excluded_test_types(
    test_types: list[dict[str, str]], excludes: list[dict[str, object]]
) -> list[str]:
    """Return errors for excludes whose test-type entry no longer matches."""
    known_test_types = {
        (entry.get("name"), entry.get("modules")) for entry in test_types
    }

    errors: list[str] = []
    for index, exclude in enumerate(excludes, start=1):
        test_type = exclude.get("test-type")
        if not isinstance(test_type, dict):
            continue

        key = (test_type.get("name"), test_type.get("modules"))
        if key not in known_test_types:
            name = test_type.get("name", "<unnamed>")
            errors.append(
                f"matrix exclude #{index} references test-type {name!r}, "
                "but its definition does not match any matrix test-type entry"
            )

    return errors


def main() -> None:
    with open(WORKFLOW_PATH) as f:
        workflow = yaml.safe_load(f)

    matrix = workflow["jobs"]["run-tests"]["strategy"]["matrix"]
    test_types: list[dict[str, str]] = matrix["test-type"]

    exclude_errors = validate_excluded_test_types(test_types, matrix.get("exclude", []))
    if exclude_errors:
        print("ERROR: Some run-tests matrix excludes are stale:")
        for error in exclude_errors:
            print(f"  {error}")
        print(
            "\nPlease update the exclude entry in "
            f"{WORKFLOW_PATH} to match the corresponding test-type matrix entry."
        )
        sys.exit(1)

    all_test_files = discover_test_files("tests")

    # Remove files under separately-handled directories
    relevant = {
        f
        for f in all_test_files
        if not any(f == sh or f.startswith(sh + "/") for sh in SEPARATELY_HANDLED)
    }

    covered: set[str] = set()
    for entry in test_types:
        paths, ignores, ignore_globs = parse_modules(entry["modules"])
        for f in relevant:
            if file_covered_by(f, paths, ignores, ignore_globs):
                covered.add(f)

    uncovered = sorted(relevant - covered)
    if uncovered:
        print(
            "ERROR: The following test files are not covered by any "
            "run-tests matrix entry in the CI workflow:"
        )
        for f in uncovered:
            print(f"  {f}")
        print(f"\nTotal uncovered: {len(uncovered)}")
        print(
            "Please update the test-type matrix in "
            f"{WORKFLOW_PATH} to include these files."
        )
        sys.exit(1)
    else:
        print(
            f"OK: All {len(relevant)} test files are covered by the run-tests matrix."
        )


if __name__ == "__main__":
    main()
