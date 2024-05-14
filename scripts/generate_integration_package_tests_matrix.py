import json
import subprocess
import sys
from typing import Dict, List, Set

PYTHON_VERSIONS = [
    "3.9",
    "3.10",
    "3.11",
    "3.12",
]

SKIP_VERSIONS = {
    "prefect-ray": ["3.12"],
}


def get_changed_packages(commit_range: str) -> List[str]:
    # Get the list of changed files in the specified commit range
    result = subprocess.run(
        ["git", "diff", "--name-only", commit_range],
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = result.stdout.split()
    # Filter for src/integrations directories
    packages: Set[str] = set()
    for file in changed_files:
        parts = file.split("/")
        if len(parts) > 1 and parts[0] == "src" and parts[1] == "integrations":
            packages.add(parts[2])
    return list(packages)


def generate_matrix(packages: List[str], python_versions: List[str]) -> Dict:
    matrix = {"include": []}
    for package in packages:
        for version in python_versions:
            if version in SKIP_VERSIONS.get(package, []):
                continue
            matrix["include"].append({"package": package, "python-version": version})
    return matrix


if __name__ == "__main__":
    # Get the range of commits to check, or use a default range
    commit_range = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1..HEAD"
    packages = get_changed_packages(commit_range=commit_range)
    matrix = generate_matrix(packages, PYTHON_VERSIONS)
    print(json.dumps(matrix))
