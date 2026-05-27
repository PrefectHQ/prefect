from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from importlib.metadata import PathDistribution
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from prefect.runner._workspace_resolver import (
    PreparedWorkspace,
    PreparedWorkspaceError,
    PreparedWorkspaceResult,
)
from prefect.runner._workspace_starter import (
    WorkspaceResolvingEngineCommandStarter,
    _find_prematerialized_python,
    _has_editable_install_at,
    _workspace_command,
    load_flow_from_prepared_workspace,
    resolve_workspace_in_subprocess,
    workspace_environment,
)
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.processutils import command_from_string

pytestmark = pytest.mark.clear_db


def _prepared_workspace(tmp_path: Path) -> PreparedWorkspace:
    workspace_root = tmp_path / "workspace"
    working_directory = workspace_root / "project"
    working_directory.mkdir(parents=True)
    return PreparedWorkspace(
        workspace_root=workspace_root,
        working_directory=working_directory,
        project_root=working_directory,
        runtime_entrypoint="flows.py:hello",
        environment={**os.environ, "WORKSPACE_TEST_ENV": "1"},
        sys_path=[str(tmp_path / "support")],
    )


def _write_pyproject(
    path: Path,
    name: str = "test-project",
    deps: str = "['prefect']",
    extra: str = "",
) -> None:
    (path / "pyproject.toml").write_text(
        f"[project]\nname = '{name}'\nversion = '0.1.0'\ndependencies = {deps}\n{extra}"
    )


def _create_fake_venv(venv_path: Path) -> str:
    """Create a minimal fake venv directory with a python executable."""
    bin_dir = venv_path / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    python.touch()
    python.chmod(0o755)
    return str(python)


def _create_dist_info(site_packages: Path, name: str, project_root: Path) -> None:
    """Create a fake dist-info directory with an editable direct_url.json."""
    dist_info = site_packages / f"{name.replace('-', '_')}-0.1.0.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(f"Name: {name}\nVersion: 0.1.0\n")
    (dist_info / "direct_url.json").write_text(
        json.dumps(
            {"url": f"file://{project_root.resolve()}", "dir_info": {"editable": True}}
        )
    )
    (dist_info / "RECORD").write_text("")


def _fake_distributions(site_packages: Path) -> Iterator[PathDistribution]:
    for path in site_packages.iterdir():
        if path.name.endswith(".dist-info"):
            yield PathDistribution(path)


def _mock_installed_distributions(
    monkeypatch: pytest.MonkeyPatch, versions: dict[str, str]
) -> None:
    normalized_versions = {
        name.lower().replace("_", "-"): version for name, version in versions.items()
    }

    def fake_distribution(name: str) -> SimpleNamespace:
        normalized_name = name.lower().replace("_", "-")
        if normalized_name not in normalized_versions:
            raise importlib.metadata.PackageNotFoundError(name)
        return SimpleNamespace(version=normalized_versions[normalized_name])

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.importlib.metadata.distribution",
        fake_distribution,
    )


def test_workspace_environment_prepends_workspace_paths(tmp_path: Path):
    workspace = _prepared_workspace(tmp_path)
    workspace.environment["PYTHONPATH"] = str(tmp_path / "existing")

    environment = workspace_environment(workspace)
    pythonpath = environment["PYTHONPATH"].split(os.pathsep)

    assert environment["WORKSPACE_TEST_ENV"] == "1"
    assert pythonpath[:3] == [
        str(workspace.working_directory),
        str(tmp_path / "support"),
        str(tmp_path / "existing"),
    ]


def _strip_venv_signals(workspace: PreparedWorkspace) -> None:
    """Remove env vars that trigger prematerialized-env detection."""
    workspace.environment.pop("VIRTUAL_ENV", None)
    workspace.environment.pop("UV_PROJECT_ENVIRONMENT", None)


def test_workspace_command_uses_uv_for_pyproject_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})
    captured_paths: list[str | None] = []

    def fake_which(executable: str, path: str | None = None) -> str | None:
        captured_paths.append(path)
        return "/opt/bin/uv" if executable == "uv" else None

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        fake_which,
    )

    command = _workspace_command(workspace, explicit_command=None)

    assert captured_paths == [workspace.environment["PATH"]]
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_falls_back_without_pyproject(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_falls_back_without_prefect_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _write_pyproject(workspace.project_root, deps="[]")
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_falls_back_without_uv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: None,
    )

    assert _workspace_command(workspace, explicit_command=None) is None


def test_workspace_command_preserves_explicit_command(tmp_path: Path):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _write_pyproject(workspace.project_root, deps="[]")

    assert (
        _workspace_command(workspace, explicit_command="python custom.py")
        == "python custom.py"
    )


def test_workspace_command_ignores_dot_venv_without_explicit_signal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """An implicit .venv at project root should not bypass uv run."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _create_fake_venv(workspace.project_root / ".venv")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_uv_project_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """When UV_PROJECT_ENVIRONMENT is set and valid, use its python."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _write_pyproject(workspace.project_root)
    custom_env = tmp_path / "custom-env"
    expected_python = _create_fake_venv(custom_env)
    workspace.environment["UV_PROJECT_ENVIRONMENT"] = str(custom_env)

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        expected_python,
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_active_virtual_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """When VIRTUAL_ENV is under project_root, use its python."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _write_pyproject(workspace.project_root)
    # Place the venv under project_root so it's credibly tied to the workspace
    active_venv = workspace.project_root / "my-venv"
    expected_python = _create_fake_venv(active_venv)
    workspace.environment["VIRTUAL_ENV"] = str(active_venv)

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        expected_python,
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_editable_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """When an editable install points at project_root, use sys.executable."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter._has_editable_install_at",
        lambda project_root, project_name: True,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    parts = command_from_string(command)
    assert parts[1:] == ["-m", "prefect.flow_engine", workspace.runtime_entrypoint]
    assert parts[0] == sys.executable


def test_workspace_command_uses_current_python_when_project_dependencies_installed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """System-installed project dependencies should skip uv run."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _strip_venv_signals(workspace)
    _write_pyproject(
        workspace.project_root,
        deps=("['prefect>=3', 'pandas>=2,<3', 'colorama; sys_platform == \"win32\"']"),
    )
    _mock_installed_distributions(
        monkeypatch,
        {
            "prefect": "3.6.0",
            "pandas": "2.2.3",
        },
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        sys.executable,
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


@pytest.mark.parametrize(
    "dependency",
    [
        "pandas[performance]>=2",
        "pandas @ https://example.com/pandas-2.2.3-py3-none-any.whl",
    ],
)
def test_workspace_command_uses_uv_for_unverifiable_project_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dependency: str
) -> None:
    """Dependencies with extras or direct URLs need uv to verify materialization."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(
        workspace.project_root,
        deps=f"['prefect>=3', '{dependency}']",
    )
    _mock_installed_distributions(
        monkeypatch,
        {
            "prefect": "3.6.0",
            "pandas": "2.2.3",
        },
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_uv_when_project_has_uv_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """uv sources can change dependency provenance without changing versions."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(
        workspace.project_root,
        deps="['prefect>=3', 'my-lib>=1']",
        extra="\n[tool.uv.sources]\nmy-lib = { path = '../my-lib' }\n",
    )
    _mock_installed_distributions(
        monkeypatch,
        {
            "prefect": "3.6.0",
            "my-lib": "1.0.0",
        },
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_uv_for_file_entrypoint_when_src_package_not_importable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """File entrypoints can still need uv to install src-layout project packages."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    package_dir = workspace.project_root / "src" / "test_project"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").touch()
    _write_pyproject(
        workspace.project_root,
        name="test-project",
        deps="['prefect>=3', 'pandas>=2,<3']",
    )
    _mock_installed_distributions(
        monkeypatch,
        {
            "prefect": "3.6.0",
            "pandas": "2.2.3",
        },
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_uv_when_module_entrypoint_needs_project_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Installed dependencies are not enough when the project module is unavailable."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.runtime_entrypoint = "package.flows:hello"
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(
        workspace.project_root,
        deps="['prefect>=3', 'pandas>=2,<3']",
    )
    _mock_installed_distributions(
        monkeypatch,
        {
            "prefect": "3.6.0",
            "pandas": "2.2.3",
        },
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_current_python_for_installed_project_outside_workspace_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """In-image project directories with installed dependencies should skip uv run."""
    workspace = _prepared_workspace(tmp_path)
    project_root = tmp_path / "prebuilt-project"
    project_root.mkdir()
    workspace.working_directory = project_root
    workspace.project_root = project_root
    assert workspace.project_root is not None
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect>=3']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        sys.executable,
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_uses_uv_for_project_outside_workspace_root_with_missing_dependencies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """In-image source alone should not bypass uv when dependencies are missing."""
    workspace = _prepared_workspace(tmp_path)
    project_root = tmp_path / "prebuilt-project"
    project_root.mkdir()
    workspace.working_directory = project_root
    workspace.project_root = project_root
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_workspace_command_falls_back_to_uv_when_no_prematerialized_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """When no credible pre-materialized env exists, fall back to uv run."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    workspace.environment["PATH"] = "/workspace/bin"
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_has_editable_install_at_returns_false_for_wrong_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Editable install pointing at a different path should not match."""
    other_root = tmp_path / "other-project"
    other_root.mkdir()
    project_root = tmp_path / "my-project"
    project_root.mkdir()

    site_packages = tmp_path / "site-packages"
    _create_dist_info(site_packages, "my-project", other_root)

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.importlib.metadata.distributions",
        lambda: _fake_distributions(site_packages),
    )

    assert _has_editable_install_at(project_root, "my-project") is False


def test_has_editable_install_at_returns_true_for_matching_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Editable install pointing at the exact project root should match."""
    project_root = tmp_path / "my-project"
    project_root.mkdir()

    site_packages = tmp_path / "site-packages"
    _create_dist_info(site_packages, "my-project", project_root)

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.importlib.metadata.distributions",
        lambda: _fake_distributions(site_packages),
    )

    assert _has_editable_install_at(project_root, "my-project") is True


def test_has_editable_install_at_skips_distributions_without_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Malformed dist-info metadata should not prevent later matches."""
    project_root = tmp_path / "my-project"
    project_root.mkdir()
    site_packages = tmp_path / "site-packages"
    (site_packages / "malformed-0.1.0.dist-info").mkdir(parents=True)
    _create_dist_info(site_packages, "my-project", project_root)

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.importlib.metadata.distributions",
        lambda: _fake_distributions(site_packages),
    )

    assert _has_editable_install_at(project_root, "my-project") is True


def test_find_prematerialized_python_prefers_uv_project_environment(
    tmp_path: Path,
):
    """UV_PROJECT_ENVIRONMENT is an explicit pre-materialized env signal."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _create_fake_venv(workspace.project_root / ".venv")
    custom_env = tmp_path / "custom-env"
    expected_python = _create_fake_venv(custom_env)
    workspace.environment["UV_PROJECT_ENVIRONMENT"] = str(custom_env)

    result = _find_prematerialized_python(workspace)
    assert result == expected_python


def test_find_prematerialized_python_returns_none_without_signals(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """No pre-materialized env signals means None."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _create_fake_venv(workspace.project_root / ".venv")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})

    result = _find_prematerialized_python(workspace)
    assert result is None


def test_unrelated_virtual_env_falls_back_to_uv_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """VIRTUAL_ENV pointing at a valid but unrelated venv should NOT skip uv run."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    workspace.environment.pop("UV_PROJECT_ENVIRONMENT", None)
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})

    # Create a valid venv outside of project_root
    unrelated_venv = tmp_path / "worker-venv"
    _create_fake_venv(unrelated_venv)
    workspace.environment["VIRTUAL_ENV"] = str(unrelated_venv)
    workspace.environment["PATH"] = "/workspace/bin"

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    command = _workspace_command(workspace, explicit_command=None)
    assert command is not None
    # Should fall back to uv run, NOT use the unrelated venv's python
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]


def test_relative_uv_project_environment_resolved_against_project_root(
    tmp_path: Path,
):
    """Relative UV_PROJECT_ENVIRONMENT is resolved against project_root."""
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _write_pyproject(workspace.project_root)

    # Create venv at project_root/my-env (using relative path "my-env")
    expected_python = _create_fake_venv(workspace.project_root / "my-env")
    workspace.environment["UV_PROJECT_ENVIRONMENT"] = "my-env"

    result = _find_prematerialized_python(workspace)
    assert result == expected_python


async def test_resolve_workspace_in_subprocess_returns_success_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    captured: dict[str, object] = {}

    async def fake_run_process(command: list[str], **kwargs: object):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=PreparedWorkspaceResult(status="success", workspace=workspace)
            .model_dump_json()
            .encode(),
            stderr=b"",
        )

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.anyio.run_process", fake_run_process
    )

    result = await resolve_workspace_in_subprocess(uuid4(), tmp_path / "workspace")

    assert result == workspace
    assert "prefect.runner._workspace_resolver" in captured["command"]
    assert captured["kwargs"]["stdout"] == subprocess.PIPE
    assert captured["kwargs"]["stderr"] == subprocess.PIPE
    assert "env" in captured["kwargs"]
    assert captured["kwargs"]["check"] is False


async def test_resolve_workspace_in_subprocess_raises_structured_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    command = ["python", "-m", "prefect.runner._workspace_resolver"]
    result = PreparedWorkspaceResult(
        status="error",
        error=PreparedWorkspaceError(
            error_type="StepExecutionError",
            error_message="pull failed",
            cause_type="RuntimeError",
            cause_message="boom",
        ),
    )

    async def fake_run_process(*args: object, **kwargs: object):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=result.model_dump_json().encode(),
            stderr=b"",
        )

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.anyio.run_process", fake_run_process
    )

    with pytest.raises(RuntimeError, match="StepExecutionError: pull failed"):
        await resolve_workspace_in_subprocess(uuid4(), tmp_path / "workspace")


async def test_workspace_resolving_starter_delegates_to_engine_starter(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    resolver = AsyncMock(return_value=workspace)
    flow_run = MagicMock()
    flow_run.id = uuid4()
    instances: list[object] = []

    class FakeEngineCommandStarter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            instances.append(self)

        async def start(self, flow_run_arg: object, task_status: object) -> None:
            self.flow_run = flow_run_arg
            self.task_status = task_status

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.resolve_workspace_in_subprocess", resolver
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.EngineCommandStarter",
        FakeEngineCommandStarter,
    )

    starter = WorkspaceResolvingEngineCommandStarter(
        workspace_root=tmp_path / "workspace-root",
        deployment_name="workspace-deployment",
    )
    await starter.start(flow_run)

    assert starter.workspace == workspace
    resolver.assert_awaited_once_with(flow_run.id, tmp_path / "workspace-root")
    assert len(instances) == 1
    engine_starter = instances[0]
    assert engine_starter.kwargs["command"] is None
    assert engine_starter.kwargs["cwd"] == workspace.working_directory
    assert engine_starter.kwargs["entrypoint"] == workspace.runtime_entrypoint
    assert engine_starter.kwargs["env"]["WORKSPACE_TEST_ENV"] == "1"
    assert engine_starter.flow_run is flow_run


async def test_workspace_resolving_starter_uses_uv_for_pyproject_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    workspace = _prepared_workspace(tmp_path)
    assert workspace.project_root is not None
    _strip_venv_signals(workspace)
    _write_pyproject(workspace.project_root, deps="['prefect', 'missing-package']")
    _mock_installed_distributions(monkeypatch, {"prefect": "3.0.0"})
    resolver = AsyncMock(return_value=workspace)
    flow_run = MagicMock()
    flow_run.id = uuid4()
    instances: list[object] = []

    class FakeEngineCommandStarter:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs
            instances.append(self)

        async def start(self, flow_run_arg: object, task_status: object) -> None:
            self.flow_run = flow_run_arg
            self.task_status = task_status

    monkeypatch.setattr(
        "prefect.runner._workspace_starter.resolve_workspace_in_subprocess", resolver
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.EngineCommandStarter",
        FakeEngineCommandStarter,
    )
    monkeypatch.setattr(
        "prefect.runner._workspace_starter.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )

    starter = WorkspaceResolvingEngineCommandStarter(
        workspace_root=tmp_path / "workspace-root",
        deployment_name="workspace-deployment",
    )
    await starter.start(flow_run)

    assert len(instances) == 1
    command = instances[0].kwargs["command"]
    assert command is not None
    assert command_from_string(command) == [
        "/opt/bin/uv",
        "run",
        "--no-dev",
        "--project",
        str(workspace.project_root),
        "-m",
        "prefect.flow_engine",
        workspace.runtime_entrypoint,
    ]
    assert instances[0].kwargs["cwd"] == workspace.working_directory
    assert instances[0].kwargs["deployment_name"] == "workspace-deployment"


async def test_load_flow_from_prepared_workspace_does_not_change_parent_cwd(
    tmp_path: Path,
):
    workspace = _prepared_workspace(tmp_path)
    flow_file = workspace.working_directory / "flows.py"
    flow_file.write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    return 'hello'\n"
    )
    parent_cwd = tmp_path / "parent-cwd"
    parent_cwd.mkdir()
    original_sys_path = list(sys.path)

    with tmpchdir(parent_cwd):
        flow = await load_flow_from_prepared_workspace(workspace)
        assert Path.cwd() == parent_cwd.resolve()

    assert flow.name == "hello"
    assert sys.path == original_sys_path


async def test_load_flow_from_prepared_workspace_preserves_module_entrypoint(
    tmp_path: Path,
):
    workspace = _prepared_workspace(tmp_path)
    package = workspace.working_directory / "package"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "module.py").write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    return 'hello'\n"
    )
    workspace.runtime_entrypoint = "package.module:hello"
    parent_cwd = tmp_path / "parent-cwd"
    parent_cwd.mkdir()
    original_sys_path = list(sys.path)

    with tmpchdir(parent_cwd):
        flow = await load_flow_from_prepared_workspace(workspace)
        assert Path.cwd() == parent_cwd.resolve()

    assert flow.name == "hello"
    assert sys.path == original_sys_path
