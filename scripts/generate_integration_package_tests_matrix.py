import json
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

PYTHON_VERSIONS = [
    "3.10",
    "3.11",
    "3.12",
    "3.13",
]

SKIP_VERSIONS: dict[str, list[str]] = {
    "prefect-ray": ["3.13"],
}

COMPAT_PYTHON_VERSION = "3.12"

INTEGRATIONS_DIR = Path(__file__).resolve().parent.parent / "src" / "integrations"


def get_compat_versions(package: str) -> dict[str, list[str]]:
    """Read [ci.compat-matrix] from the package's pyproject.toml."""
    pyproject = INTEGRATIONS_DIR / package / "pyproject.toml"
    if not pyproject.exists():
        return {}
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    return data.get("ci", {}).get("compat-matrix", {})


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
            matrix["include"].append(
                {
                    "package": package,
                    "python-version": version,
                    "dependency-override": "",
                }
            )
        # Add compat-version entries from [ci.compat-matrix]
        for dep, versions in get_compat_versions(package).items():
            for dep_version in versions:
                matrix["include"].append(
                    {
                        "package": package,
                        "python-version": COMPAT_PYTHON_VERSION,
                        "dependency-override": f"{dep}=={dep_version}",
                    }
                )
    return matrix


if __name__ == "__main__":
    # Get the range of commits to check, or use a default range
    commit_range = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1..HEAD"
    packages = get_changed_packages(commit_range=commit_range)
    matrix = generate_matrix(packages, PYTHON_VERSIONS)
    print(json.dumps(matrix))
