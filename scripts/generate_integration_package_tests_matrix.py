#!/usr/bin/env python3./
import json
import subprocess
import sys

PYTHON_VERSIONS = [
    "3.8",
    "3.9",
    "3.10",
    "3.11",
    "3.12",
]


def get_changed_packages():
    # Get the range of commits to check, or use a default range
    commit_range = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1..HEAD"
    # Get the list of changed files in the specified commit range
    result = subprocess.run(
        ["git", "diff", "--name-only", commit_range], capture_output=True, text=True
    )
    changed_files = result.stdout.split()
    # Filter for src/integrations directories
    packages = set()
    for file in changed_files:
        parts = file.split("/")
        if len(parts) > 1 and parts[0] == "src" and parts[1] == "integrations":
            packages.add(parts[2])
    return list(packages)


def generate_matrix(packages, python_versions):
    matrix = {"include": []}
    for package in packages:
        for version in python_versions:
            matrix["include"].append({"package": package, "python-version": version})
    return matrix


if __name__ == "__main__":
    packages = get_changed_packages()
    matrix = generate_matrix(packages, PYTHON_VERSIONS)
    print(json.dumps(matrix))
