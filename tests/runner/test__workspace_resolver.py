from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.filesystems import LocalFileSystem
from prefect.runner._workspace_resolver import (
    PreparedWorkspaceResult,
    _find_project_root,
    get_workspace_resolver_command,
)
from prefect.runner.storage import BlockStorageAdapter, RemoteStorage
from prefect.settings import get_current_settings
from prefect.utilities.filesystem import tmpchdir

pytestmark = pytest.mark.clear_db

REPO_ROOT = Path(__file__).resolve().parents[2]
CUSTOM_STEP_FQN = "tests.utilities.workspace_resolver_steps"


def _run_workspace_resolver(
    flow_run_id, workspace_root: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        **get_current_settings().to_environment_variables(exclude_unset=True),
        **(extra_env or {}),
    }
    pythonpath = str(REPO_ROOT)
    if env.get("PYTHONPATH"):
        pythonpath = f"{pythonpath}{os.pathsep}{env['PYTHONPATH']}"
    env["PYTHONPATH"] = pythonpath

    return subprocess.run(
        get_workspace_resolver_command(flow_run_id, workspace_root),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _parse_result(process: subprocess.CompletedProcess[str]) -> PreparedWorkspaceResult:
    assert process.stdout, process.stderr
    return PreparedWorkspaceResult.model_validate_json(process.stdout)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def _create_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init")
    _git(path, "config", "user.email", "workspace-resolver@example.com")
    _git(path, "config", "user.name", "Workspace Resolver")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "initial")


@pytest.mark.timeout(60)
class TestWorkspaceResolverProcess:
    async def test_resolves_absolute_set_working_directory_project_root(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "local-project"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'local'\n"
        )
        local_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'local-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("local-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="local-storage-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(local_project)
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(flow_run.id, tmp_path / "local-workspace")
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == local_project.resolve()
        assert result.workspace.project_root == local_project.resolve()

    async def test_materializes_relative_local_deployment_path_into_workspace(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "relative-source-project"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'relative'\n"
        )
        local_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'relative-source-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("relative-local-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="relative-local-storage-deployment",
            entrypoint="flows/hello.py:hello",
            path=".",
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "relative-local-workspace"
        with tmpchdir(local_project):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == local_project.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == workspace_root.resolve()
        assert result.workspace.project_root == workspace_root.resolve()
        assert (workspace_root / "flows" / "hello.py").read_text() == (
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'relative'\n"
        )

    async def test_pull_steps_without_directory_output_materialize_source_into_workspace(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "setup-step-project"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'setup'\n"
        )
        local_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'setup-step-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("setup-step-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="setup-step-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.run_shell_script": {
                        "script": "echo setup complete",
                        "stream_output": False,
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "setup-step-workspace"
        with tmpchdir(local_project):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == local_project.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == workspace_root.resolve()
        assert result.workspace.project_root == workspace_root.resolve()
        assert (workspace_root / "flows" / "hello.py").read_text() == (
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'setup'\n"
        )

    async def test_pull_steps_without_directory_output_keep_workspace_when_entrypoint_created_there(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        workspace_writer = tmp_path / "write_workspace_flow.py"
        workspace_writer.write_text(
            "from pathlib import Path\n"
            "Path('flows').mkdir(parents=True, exist_ok=True)\n"
            "Path('flows/hello.py').write_text("
            '"from prefect import flow\\n\\n'
            "@flow\\ndef hello():\\n    return 'workspace'\\n\""
            ")\n"
            "Path('pyproject.toml').write_text("
            "\"[project]\\nname = 'workspace-project'\\nversion = '0.1.0'\\n\""
            ")\n"
        )

        flow_id = await prefect_client.create_flow_from_name("workspace-step-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="workspace-step-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.run_shell_script": {
                        "script": f"{sys.executable} {workspace_writer}",
                        "stream_output": False,
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        caller_project = tmp_path / "caller-project"
        caller_flow = caller_project / "flows" / "hello.py"
        caller_flow.parent.mkdir(parents=True)
        caller_flow.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'caller'\n"
        )

        workspace_root = tmp_path / "workspace-step-workspace"
        with tmpchdir(caller_project):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == caller_project.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == workspace_root.resolve()
        assert result.workspace.project_root == workspace_root.resolve()
        assert (workspace_root / "flows" / "hello.py").read_text() == (
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'workspace'\n"
        )

    async def test_resolves_local_deployment_path_in_place_without_storage(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "image-app"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'image-local'\n"
        )
        local_project.joinpath(".prefectignore").write_text("flows/\n")
        local_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'image-app'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("image-local-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="image-local-deployment",
            entrypoint="flows/hello.py:hello",
            path=str(local_project),
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "image-local-workspace"
        process = _run_workspace_resolver(flow_run.id, workspace_root)
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == local_project.resolve()
        assert result.workspace.project_root == local_project.resolve()
        assert not (workspace_root / "flows" / "hello.py").exists()

    async def test_resolves_storage_base_path_into_matching_workspace_directory(
        self,
        prefect_client,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        storage_base = tmp_path / "runner-storage-base"
        storage_destination = storage_base / "stored-project"
        flow_file = storage_destination / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'stored'\n"
        )
        storage_destination.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'stored-project'\nversion = '0.1.0'\n"
        )
        monkeypatch.setenv("PREFECT__STORAGE_BASE_PATH", str(storage_base))

        flow_id = await prefect_client.create_flow_from_name("stored-local-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="stored-local-storage-deployment",
            entrypoint="flows/hello.py:hello",
            path="$STORAGE_BASE_PATH/stored-project",
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "stored-local-workspace"
        unrelated_cwd = tmp_path / "unrelated-cwd"
        unrelated_cwd.mkdir()
        with tmpchdir(unrelated_cwd):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == unrelated_cwd.resolve()

        result = _parse_result(process)
        workspace_project = workspace_root / "stored-project"

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == workspace_project.resolve()
        assert result.workspace.project_root == workspace_project.resolve()
        assert (workspace_project / "flows" / "hello.py").read_text() == (
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'stored'\n"
        )
        assert not (workspace_root / "flows" / "hello.py").exists()

    async def test_resolves_git_clone_with_chained_working_directory_and_custom_step(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        source_repo = tmp_path / "source-repo"
        flow_file = source_repo / "service" / "src" / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'hi'\n"
        )
        (source_repo / "service" / "pyproject.toml").write_text(
            "[project]\nname = 'workspace-resolver-test'\nversion = '0.1.0'\n"
        )
        _create_git_repo(source_repo)

        flow_id = await prefect_client.create_flow_from_name("hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="git-clone-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.git_clone": {
                        "id": "clone",
                        "repository": source_repo.as_uri(),
                        "clone_directory_name": "checkout",
                    }
                },
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "{{ clone.directory }}/service"
                    }
                },
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "src"
                    }
                },
                {
                    f"{CUSTOM_STEP_FQN}.write_marker": {
                        "filename": "marker.txt",
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        parent_cwd = tmp_path / "parent-cwd"
        parent_cwd.mkdir()
        workspace_root = tmp_path / "workspace"

        with tmpchdir(parent_cwd):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == parent_cwd.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.workspace_root == workspace_root.resolve()
        assert (
            result.workspace.working_directory
            == (workspace_root / "checkout" / "service" / "src").resolve()
        )
        assert (
            result.workspace.project_root
            == (workspace_root / "checkout" / "service").resolve()
        )
        assert result.workspace.runtime_entrypoint == "flows/hello.py:hello"
        marker = result.workspace.working_directory / "marker.txt"
        assert marker.read_text() == str(result.workspace.working_directory)

    async def test_tracks_relative_directory_output_from_custom_chdir_step(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        flow_id = await prefect_client.create_flow_from_name("custom-chdir")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="custom-chdir-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.make_directory_and_change_directory": {
                        "directory": "src",
                        "return_directory": ".",
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "custom-chdir-workspace"
        process = _run_workspace_resolver(flow_run.id, workspace_root)
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == (workspace_root / "src").resolve()

    async def test_empty_directory_output_does_not_override_workspace_fallback(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        flow_id = await prefect_client.create_flow_from_name("empty-directory-output")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="empty-directory-output-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.return_empty_directory": {},
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "empty-directory-output-workspace"
        process = _run_workspace_resolver(flow_run.id, workspace_root)
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == workspace_root.resolve()

    async def test_later_custom_chdir_overrides_stale_directory_output(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        flow_id = await prefect_client.create_flow_from_name("custom-chdir-stale")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="custom-chdir-stale-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.make_directory_and_change_directory": {
                        "directory": "src",
                        "return_directory": ".",
                    }
                },
                {
                    f"{CUSTOM_STEP_FQN}.make_directory_and_change_directory": {
                        "directory": "../actual",
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "custom-stale-workspace"
        process = _run_workspace_resolver(flow_run.id, workspace_root)
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert (
            result.workspace.working_directory == (workspace_root / "actual").resolve()
        )

    async def test_captures_environment_and_sys_path_mutations(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "process-state-project"
        support_dir = local_project / "support"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        support_dir.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'state'\n"
        )
        local_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'process-state-project'\nversion = '0.1.0'\n"
        )

        env_var_name = "WORKSPACE_RESOLVER_TEST_ENV"
        env_var_value = "configured"

        flow_id = await prefect_client.create_flow_from_name("process-state-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="process-state-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(local_project)
                    }
                },
                {
                    f"{CUSTOM_STEP_FQN}.set_environment_variable": {
                        "name": env_var_name,
                        "value": env_var_value,
                    }
                },
                {
                    f"{CUSTOM_STEP_FQN}.prepend_to_sys_path": {
                        "path": "support",
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(
            flow_run.id, tmp_path / "process-state-workspace"
        )
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.environment[env_var_name] == env_var_value
        assert result.workspace.sys_path[0] == str(support_dir.resolve())
        assert os.environ.get(env_var_name) is None

    async def test_uses_absolute_directory_output_when_step_removed_cwd(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        recovered_project = tmp_path / "recovered-project"
        flow_file = recovered_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'recovered'\n"
        )
        recovered_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'recovered-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("removed-cwd-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="removed-cwd-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.remove_current_directory": {
                        "return_directory": str(recovered_project)
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(
            flow_run.id, tmp_path / "removed-cwd-workspace"
        )
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == recovered_project.resolve()
        assert result.workspace.project_root == recovered_project.resolve()

    async def test_resolves_remote_storage_pull_without_changing_parent_cwd(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        remote_source = tmp_path / "remote-source"
        flow_file = remote_source / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'remote'\n"
        )
        (remote_source / "pyproject.toml").write_text(
            "[project]\nname = 'remote-source'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("remote-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="remote-storage-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.pull_from_remote_storage": {
                        "url": remote_source.as_uri()
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        parent_cwd = tmp_path / "remote-parent-cwd"
        parent_cwd.mkdir()
        workspace_root = tmp_path / "remote-workspace"

        with tmpchdir(parent_cwd):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == parent_cwd.resolve()

        result = _parse_result(process)
        expected_storage = RemoteStorage(url=remote_source.as_uri())
        expected_storage.set_base_path(workspace_root.resolve())

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == expected_storage.destination
        assert result.workspace.project_root is None

    async def test_resolves_block_pull_step(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        block_source = tmp_path / "block-source"
        flow_file = block_source / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'block'\n"
        )
        (block_source / "pyproject.toml").write_text(
            "[project]\nname = 'block-source'\nversion = '0.1.0'\n"
        )

        block_name = f"workspace-resolver-{uuid4()}"
        await LocalFileSystem(basepath=str(block_source)).save(
            block_name,
            overwrite=True,
        )

        flow_id = await prefect_client.create_flow_from_name("block-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="block-storage-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.pull_with_block": {
                        "block_document_name": block_name,
                        "block_type_slug": LocalFileSystem.get_block_type_slug(),
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(flow_run.id, tmp_path / "block-workspace")
        result = _parse_result(process)
        expected_storage = BlockStorageAdapter(
            LocalFileSystem.load(block_name, _sync=True)
        )
        expected_storage.set_base_path((tmp_path / "block-workspace").resolve())

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == expected_storage.destination
        assert result.workspace.project_root == expected_storage.destination

    async def test_returns_structured_failure_payload(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        flow_id = await prefect_client.create_flow_from_name("broken-flow")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="broken-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.raise_error": {
                        "message": "resolver exploded",
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(flow_run.id, tmp_path / "broken-workspace")
        result = _parse_result(process)

        assert process.returncode == 1
        assert result.status == "error"
        assert result.error is not None
        assert result.error.error_type == "StepExecutionError"
        assert "Encountered error while running" in result.error.error_message
        assert result.error.cause_type == "RuntimeError"
        assert result.error.cause_message == "resolver exploded"
        assert "resolver exploded" in process.stderr

    async def test_keeps_stdout_reserved_for_json_payload(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "noisy-project"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'noisy'\n"
        )
        local_project.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'noisy-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("noisy-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="noisy-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.emit_inherited_stdout": {
                        "message": "resolver-step-noise",
                    }
                },
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(local_project)
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(flow_run.id, tmp_path / "noisy-workspace")
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert "resolver-step-noise" in process.stderr
        assert "resolver-step-noise" not in process.stdout
        assert result.workspace is not None
        assert result.workspace.project_root == local_project.resolve()

    async def test_pull_step_logs_are_sent_to_the_api(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        local_project = tmp_path / "logged-project"
        flow_file = local_project / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'logged'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("logged-hello")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="logged-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": str(local_project)
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(
            flow_run.id,
            tmp_path / "logged-workspace",
            # The test session disables API logging globally; the subprocess must
            # have it on to exercise log delivery.
            extra_env={"PREFECT_LOGGING_TO_API_ENABLED": "True"},
        )
        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"

        logs = await prefect_client.read_logs(
            log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=[flow_run.id]))
        )
        messages = [log.message for log in logs]
        assert "Running 1 deployment pull step(s)" in messages
        assert "Executing deployment step: set_working_directory" in messages
        assert (
            "Deployment step 'set_working_directory' completed successfully" in messages
        )

    async def test_pull_step_logs_are_sent_to_the_api_when_a_step_fails(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        flow_id = await prefect_client.create_flow_from_name("failing-logged-flow")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="failing-logged-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    f"{CUSTOM_STEP_FQN}.raise_error": {
                        "message": "resolver exploded",
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        process = _run_workspace_resolver(
            flow_run.id,
            tmp_path / "failing-workspace",
            extra_env={"PREFECT_LOGGING_TO_API_ENABLED": "True"},
        )
        result = _parse_result(process)

        assert process.returncode == 1
        assert result.status == "error"

        logs = await prefect_client.read_logs(
            log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=[flow_run.id]))
        )
        messages = [log.message for log in logs]
        assert "Executing deployment step: raise_error" in messages


class TestRelativePathSetWorkingDirectory:
    """Tests for set_working_directory with relative paths resolving to the
    original process CWD (e.g. the container WORKDIR) rather than the
    temporary workspace root.  Regression tests for OSS-8050."""

    async def test_relative_dot_resolves_to_original_cwd(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        container_workdir = tmp_path / "container-workdir"
        flow_file = container_workdir / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'cwd'\n"
        )
        container_workdir.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'cwd-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("relative-dot")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="relative-dot-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {"prefect.deployments.steps.set_working_directory": {"directory": "."}}
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "dot-workspace"
        with tmpchdir(container_workdir):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == container_workdir.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == container_workdir.resolve()
        assert result.workspace.project_root == container_workdir.resolve()

    async def test_relative_subdir_resolves_to_original_cwd(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        container_workdir = tmp_path / "container-workdir"
        subdir = container_workdir / "app"
        flow_file = subdir / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'sub'\n"
        )
        subdir.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'subdir-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("relative-subdir")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="relative-subdir-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "app"
                    }
                }
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "subdir-workspace"
        with tmpchdir(container_workdir):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == container_workdir.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == subdir.resolve()
        assert result.workspace.project_root == subdir.resolve()

    async def test_relative_path_after_git_clone_resolves_to_clone_directory(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        """When git_clone runs before set_working_directory, the relative path
        in set_working_directory should resolve against the clone directory CWD
        rather than the original process CWD."""
        source_repo = tmp_path / "source-repo"
        flow_file = source_repo / "service" / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'chained'\n"
        )
        (source_repo / "service" / "pyproject.toml").write_text(
            "[project]\nname = 'chained-project'\nversion = '0.1.0'\n"
        )
        _create_git_repo(source_repo)

        flow_id = await prefect_client.create_flow_from_name("chained-relative")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="chained-relative-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.git_clone": {
                        "id": "clone",
                        "repository": source_repo.as_uri(),
                        "clone_directory_name": "checkout",
                    }
                },
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "{{ clone.directory }}/service"
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        parent_cwd = tmp_path / "parent-cwd"
        parent_cwd.mkdir()
        workspace_root = tmp_path / "chained-workspace"

        with tmpchdir(parent_cwd):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == parent_cwd.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert (
            result.workspace.working_directory
            == (workspace_root / "checkout" / "service").resolve()
        )
        assert (
            result.workspace.project_root
            == (workspace_root / "checkout" / "service").resolve()
        )

    async def test_relative_dot_with_run_shell_script_resolves_to_original_cwd(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        """Reproduces the exact scenario from the bug report: set_working_directory
        with '.' followed by run_shell_script should run from the original CWD."""
        container_workdir = tmp_path / "container-workdir"
        flow_file = container_workdir / "flows" / "hello.py"
        flow_file.parent.mkdir(parents=True, exist_ok=True)
        flow_file.write_text(
            "from prefect import flow\n\n@flow\ndef hello():\n    return 'shell'\n"
        )
        container_workdir.joinpath("pyproject.toml").write_text(
            "[project]\nname = 'shell-project'\nversion = '0.1.0'\n"
        )

        flow_id = await prefect_client.create_flow_from_name("shell-relative")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="shell-relative-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {"prefect.deployments.steps.set_working_directory": {"directory": "."}},
                {
                    "prefect.deployments.steps.run_shell_script": {
                        "script": "echo 'setup complete'",
                        "stream_output": False,
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        workspace_root = tmp_path / "shell-workspace"
        with tmpchdir(container_workdir):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == container_workdir.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        assert result.workspace.working_directory == container_workdir.resolve()
        assert result.workspace.project_root == container_workdir.resolve()

    async def test_run_shell_script_then_set_working_directory_resolves_workspace_relative(
        self,
        prefect_client,
        tmp_path: Path,
    ) -> None:
        """When run_shell_script creates a directory in the workspace and
        set_working_directory follows with a relative path, the path must
        resolve against the workspace CWD — not the original process CWD."""
        container_workdir = tmp_path / "container-workdir"
        container_workdir.mkdir()

        # Write a helper script that creates workspace content
        setup_script = tmp_path / "setup.sh"
        setup_script.write_text(
            "#!/bin/sh\n"
            "mkdir -p generated/flows\n"
            'printf "from prefect import flow\\n\\n'
            '@flow\\ndef hello():\\n    return 42\\n" '
            "> generated/flows/hello.py\n"
            'printf "[project]\\nname = \\"gen\\"\\nversion = \\"0.1.0\\"\\n" '
            "> generated/pyproject.toml\n"
        )
        setup_script.chmod(0o755)

        workspace_root = tmp_path / "composition-workspace"

        flow_id = await prefect_client.create_flow_from_name("composition-relative")
        deployment_id = await prefect_client.create_deployment(
            flow_id=flow_id,
            name="composition-relative-deployment",
            entrypoint="flows/hello.py:hello",
            pull_steps=[
                {
                    "prefect.deployments.steps.run_shell_script": {
                        "script": str(setup_script),
                        "stream_output": False,
                    }
                },
                {
                    "prefect.deployments.steps.set_working_directory": {
                        "directory": "generated"
                    }
                },
            ],
        )
        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        with tmpchdir(container_workdir):
            process = _run_workspace_resolver(flow_run.id, workspace_root)
            assert Path.cwd() == container_workdir.resolve()

        result = _parse_result(process)

        assert process.returncode == 0, process.stderr
        assert result.status == "success"
        assert result.workspace is not None
        # The directory should be workspace-relative, NOT container_workdir-relative
        assert (
            result.workspace.working_directory
            == (workspace_root / "generated").resolve()
        )


class TestProjectRootDetection:
    def test_does_not_walk_above_workspace_root(self, tmp_path: Path) -> None:
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname = 'outside-workspace'\nversion = '0.1.0'\n"
        )

        assert _find_project_root(workspace_root, workspace_root) is None

    def test_returns_project_root_for_absolute_working_directory_outside_workspace_root(
        self, tmp_path: Path
    ) -> None:
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        outside_project = tmp_path / "outside"
        nested_directory = outside_project / "src"
        nested_directory.mkdir(parents=True)
        (outside_project / "pyproject.toml").write_text(
            "[project]\nname = 'outside'\nversion = '0.1.0'\n"
        )

        assert _find_project_root(nested_directory, workspace_root) == outside_project
