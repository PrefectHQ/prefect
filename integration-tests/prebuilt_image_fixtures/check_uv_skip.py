"""Runs inside the pre-built container to verify detection logic.

Checks that importlib.metadata can find the project declared in
pyproject.toml — the same mechanism _project_is_installed uses.
"""

import importlib.metadata
import json
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib

from pathlib import Path

pyproject = Path("/opt/prefect/flow/pyproject.toml")
data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
project_name = data["project"]["name"]

try:
    dist = importlib.metadata.distribution(project_name)
    installed = True
    version = dist.version
except importlib.metadata.PackageNotFoundError:
    installed = False
    version = None

print(
    json.dumps(
        {
            "project_name": project_name,
            "installed": installed,
            "version": version,
        }
    )
)
