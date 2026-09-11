"""Auto-`uv run` launcher command construction shared by runner and worker paths."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

from prefect._internal.compatibility.backports import tomllib
from prefect.settings import get_current_settings
from prefect.utilities.processutils import command_to_string


def _dependencies_include_prefect(dependencies: object) -> bool:
    if not isinstance(dependencies, Iterable) or isinstance(dependencies, (str, bytes)):
        return False

    for dependency in dependencies:
        if not isinstance(dependency, str):
            continue
        try:
            name = Requirement(dependency).name
        except InvalidRequirement:
            continue
        if canonicalize_name(name) == "prefect":
            return True
    return False


def _pyproject_declares_prefect_dependency(pyproject: Path) -> bool:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return False

    project = data.get("project")
    if not isinstance(project, dict):
        return False

    return _dependencies_include_prefect(project.get("dependencies"))


def uv_project_command(
    project_root: Path | None,
    engine_args: Iterable[str],
    path: str | None = None,
    auto_install_dependencies: bool | None = None,
) -> str | None:
    """Build an auto-`uv run` command for a project directory, if applicable.

    Returns `None` unless dependency auto-installation is enabled, `project_root`
    contains a `pyproject.toml` declaring `prefect` as a project dependency, and
    `uv` is discoverable on `path` (or the current `PATH` when `path` is `None`).

    `auto_install_dependencies` overrides the current setting value, for callers
    that resolve the setting from a run-specific environment.
    """
    if auto_install_dependencies is None:
        auto_install_dependencies = (
            get_current_settings().runner.auto_install_dependencies
        )
    if not auto_install_dependencies:
        return None

    if project_root is None:
        return None

    pyproject = project_root / "pyproject.toml"
    if not pyproject.is_file() or not _pyproject_declares_prefect_dependency(pyproject):
        return None

    uv_executable = (
        shutil.which("uv", path=path) if path is not None else shutil.which("uv")
    )
    if uv_executable is None:
        return None

    return command_to_string(
        [
            uv_executable,
            "run",
            "--no-default-groups",
            "--project",
            str(project_root),
            *engine_args,
        ]
    )
