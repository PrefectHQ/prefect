import json
import subprocess
import sys

PYTHON_VERSIONS = [
    "3.9",
    "3.10",
    "3.11",
    "3.12",
    "3.13",
]

SKIP_VERSIONS: dict[str, list[str]] = {
    "prefect-ray": ["3.13"],
}


def get_changed_packages(commit_range: str) -> list[str]:
    # Get the list of changed files in the specified commit range
    result = subprocess.run(
        ["git", "diff", "--name-only", commit_range],
        capture_output=True,
        text=True,
        check=True,
    )
    changed_files = result.stdout.split()
    # Filter for src/integrations directories
    packages: set[str] = set()
    for file in changed_files:
        parts = file.split("/")
        if len(parts) > 2 and parts[0] == "src" and parts[1] == "integrations":
            # Only add if it's a directory (has more parts after the package name)
            # and starts with "prefect-" which is the pattern for integration packages
            package_name = parts[2]
            if package_name.startswith("prefect-"):
                packages.add(package_name)
    return list(packages)


def generate_matrix(
    packages: list[str], python_versions: list[str]
) -> dict[str, list[dict[str, str]]]:
    matrix: dict[str, list[dict[str, str]]] = {"include": []}
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
