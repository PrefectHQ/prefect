from __future__ import annotations

import shutil
from pathlib import Path
from unittest import mock
from uuid import uuid4

import pytest

import prefect
from prefect._versioning import GitVersionInfo
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import VersionInfo
from prefect.deployments.base import initialize_project
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.filesystem import tmpchdir
from prefect.utilities.hashing import file_hash

TEST_PROJECTS_DIR = prefect.__development_base_path__ / "tests" / "test-projects"


@pytest.fixture(autouse=True)
def project_dir(tmp_path: Path):
    with tmpchdir(str(tmp_path)):
        shutil.copytree(TEST_PROJECTS_DIR, tmp_path, dirs_exist_ok=True)
        prefect_home = tmp_path / ".prefect"
        prefect_home.mkdir(exist_ok=True, mode=0o0700)
        initialize_project()
        yield tmp_path


@pytest.fixture(autouse=True)
async def work_pool(project_dir: Path, prefect_client: PrefectClient):
    await prefect_client.create_work_pool(WorkPoolCreate(name="test-pool", type="test"))


@pytest.fixture
async def mock_create_deployment():
    with mock.patch(
        "prefect.client.orchestration.PrefectClient.create_deployment"
    ) as mock_create:
        mock_create.return_value = uuid4()
        yield mock_create


async def test_deploy_with_simple_version(mock_create_deployment: mock.AsyncMock):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=(
            "deploy ./flows/hello.py:my_flow -n test-name -p test-pool "
            "--version '1.2.3'"
        ),
        expected_code=0,
        expected_output_contains=[
            "An important name/test-name",
            "prefect worker start --pool 'test-pool'",
        ],
    )

    mock_create_deployment.assert_awaited_once()

    passed_version = mock_create_deployment.call_args.kwargs["version"]
    passed_version_info = mock_create_deployment.call_args.kwargs["version_info"]

    assert passed_version == "1.2.3"
    assert passed_version_info == VersionInfo(
        type="prefect:simple",
        version="1.2.3",
    )


@pytest.fixture
async def mock_get_inferred_version_info():
    with mock.patch(
        "prefect.deployments.runner.get_inferred_version_info"
    ) as mock_get_inferred:
        mock_get_inferred.return_value = GitVersionInfo(
            type="vcs:git",
            version="abcdef12",
            commit_sha="abcdef12",
            message="Initial commit",
            branch="main",
            url="https://github.com/org/repo",
            repository="org/repo",
        )
        yield mock_get_inferred


async def test_deploy_with_inferred_version(
    mock_create_deployment: mock.AsyncMock,
    mock_get_inferred_version_info: mock.AsyncMock,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=(
            "deploy ./flows/hello.py:my_flow -n test-name -p test-pool "
            "--version-type vcs:git"
        ),
        expected_code=0,
        expected_output_contains=[
            "An important name/test-name",
            "prefect worker start --pool 'test-pool'",
        ],
    )

    mock_get_inferred_version_info.assert_awaited_once()
    mock_create_deployment.assert_awaited_once()

    passed_version_info = mock_create_deployment.call_args.kwargs["version_info"]

    assert passed_version_info == VersionInfo(
        type="vcs:git",
        version="abcdef12",
        commit_sha="abcdef12",
        message="Initial commit",
        branch="main",
        url="https://github.com/org/repo",
        repository="org/repo",
    )


async def test_deploy_with_inferred_version_and_version_name(
    mock_create_deployment: mock.AsyncMock,
    mock_get_inferred_version_info: mock.AsyncMock,
):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=(
            "deploy ./flows/hello.py:my_flow -n test-name -p test-pool "
            "--version-type vcs:git --version 'my-version-name'"
        ),
        expected_code=0,
        expected_output_contains=[
            "An important name/test-name",
            "prefect worker start --pool 'test-pool'",
        ],
    )

    mock_get_inferred_version_info.assert_awaited_once()
    mock_create_deployment.assert_awaited_once()

    passed_version_info = mock_create_deployment.call_args.kwargs["version_info"]

    assert passed_version_info == GitVersionInfo(
        type="vcs:git",
        version="my-version-name",
        commit_sha="abcdef12",
        message="Initial commit",
        branch="main",
        url="https://github.com/org/repo",
        repository="org/repo",
    )


async def test_deploy_with_simple_type_and_no_version_uses_flow_version(
    mock_create_deployment: mock.AsyncMock,
    project_dir: Path,
):
    # Calculate the expected version hash
    flow_file = project_dir / "flows" / "hello.py"
    expected_version = file_hash(str(flow_file))

    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=(
            "deploy ./flows/hello.py:my_flow -n test-name -p test-pool "
            "--version-type prefect:simple"
        ),
        expected_code=0,
        expected_output_contains=[
            "An important name/test-name",
            "prefect worker start --pool 'test-pool'",
        ],
    )

    mock_create_deployment.assert_awaited_once()

    passed_version_info = mock_create_deployment.call_args.kwargs["version_info"]

    assert passed_version_info == VersionInfo(
        type="prefect:simple",
        version=expected_version,
    )
