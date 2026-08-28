import json
import os
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import anyio
import anyio.abc
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import prefect
from prefect import flow
from prefect.client import schemas as client_schemas
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas import State
from prefect.client.schemas.objects import Deployment, FlowRun, StateType, WorkPool
from prefect.flows import bind_flow_to_infrastructure
from prefect.runner import _workspace_starter
from prefect.runner._process_manager import ProcessHandle
from prefect.server import models
from prefect.server.database.orm_models import Flow
from prefect.server.schemas.actions import (
    DeploymentUpdate,
    WorkPoolCreate,
)
from prefect.settings import (
    PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES,
    temporary_settings,
)
from prefect.types._datetime import now
from prefect.utilities.processutils import command_to_string
from prefect.workers.process import (
    ProcessWorker,
    ProcessWorkerResult,
)

pytestmark = pytest.mark.clear_db


@flow
def example_process_worker_flow():
    return 1


@pytest.fixture
def patch_run_process(monkeypatch: pytest.MonkeyPatch):
    def patch_run_process(returncode: int = 0, pid: int = 1000):
        mock_run_process = AsyncMock()
        mock_process = MagicMock()
        mock_process.returncode = returncode
        mock_process.pid = pid
        mock_run_process.return_value = mock_process

        monkeypatch.setattr(
            "prefect.workers.process.Runner._run_process", mock_run_process
        )

        return mock_run_process

    return patch_run_process


@pytest.fixture
async def deployment(prefect_client: PrefectClient, flow: Flow):
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow.id,
        name=f"test-process-worker-deployment-{uuid.uuid4()}",
        path=str(
            prefect.__development_base_path__
            / "tests"
            / "test-projects"
            / "import-project"
        ),
        entrypoint="my_module/flow.py:test_flow",
    )
    return await prefect_client.read_deployment(deployment_id)


@pytest.fixture
async def flow_run(deployment: Deployment, prefect_client: PrefectClient):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=now("UTC") - timedelta(minutes=5)
            ),
        ),
    )

    return flow_run


@pytest.fixture
async def deployment_with_overrides(prefect_client: PrefectClient, flow: Flow):
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow.id,
        name=f"test-process-worker-deployment-{uuid.uuid4()}",
        path=str(
            prefect.__development_base_path__
            / "tests"
            / "test-projects"
            / "import-project"
        ),
        entrypoint="my_module/flow.py:test_flow",
        job_variables={
            "command": "echo hello",
            "env": {"NEW_ENV_VAR": "from_deployment"},
            "working_dir": "/tmp/test",
        },
    )
    deployment = await prefect_client.read_deployment(deployment_id)
    return deployment


@pytest.fixture
async def flow_run_with_deployment_overrides(
    deployment_with_overrides: Deployment, prefect_client: PrefectClient
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_with_overrides.id,
        state=State(type=client_schemas.StateType.SCHEDULED),
    )
    return flow_run


@pytest.fixture
async def flow_run_with_overrides(
    deployment: Deployment, prefect_client: PrefectClient
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=now("UTC") - timedelta(minutes=5)
            ),
        ),
    )
    await prefect_client.update_flow_run(
        flow_run_id=flow_run.id,
        job_variables={"working_dir": "/tmp/test"},
    )
    return await prefect_client.read_flow_run(flow_run.id)


@pytest.fixture
def mock_open_process(monkeypatch: pytest.MonkeyPatch):
    if sys.platform == "win32":
        monkeypatch.setattr(
            "prefect.utilities.processutils._open_anyio_process", AsyncMock()
        )
        prefect.utilities.processutils._open_anyio_process.return_value.terminate = (  # noqa
            MagicMock()
        )

        yield prefect.utilities.processutils._open_anyio_process  # noqa
    else:
        mock_open_process = AsyncMock()
        monkeypatch.setattr("anyio.open_process", mock_open_process)
        mock_open_process.return_value.terminate = MagicMock()  # noqa

        yield mock_open_process


@pytest.fixture
def mock_workspace_starter(monkeypatch: pytest.MonkeyPatch):
    mock_process = MagicMock(returncode=0, pid=1000)
    handle = ProcessHandle(mock_process)
    starter = MagicMock()

    async def start(_flow_run, task_status=anyio.TASK_STATUS_IGNORED):
        task_status.started(handle)

    starter.start = AsyncMock(side_effect=start)
    starter.hook_runner.run_cancellation_hooks = AsyncMock()
    starter.hook_runner.run_crashed_hooks = AsyncMock()
    starter_factory = MagicMock(return_value=starter)
    monkeypatch.setattr(
        "prefect.workers.process.WorkspaceResolvingEngineCommandStarter",
        starter_factory,
    )
    return starter_factory


@pytest.fixture
def mock_engine_starter(monkeypatch: pytest.MonkeyPatch):
    mock_process = MagicMock(returncode=0, pid=1000)
    handle = ProcessHandle(mock_process)
    starter = MagicMock()

    async def start(_flow_run, task_status=anyio.TASK_STATUS_IGNORED):
        task_status.started(handle)

    starter.start = AsyncMock(side_effect=start)
    starter_factory = MagicMock(return_value=starter)
    monkeypatch.setattr(
        "prefect.workers.process.EngineCommandStarter",
        starter_factory,
        raising=False,
    )
    return starter_factory


@pytest.fixture
def fake_uv(tmp_path: Path) -> tuple[Path, Path]:
    bin_directory = tmp_path / "fake-bin"
    bin_directory.mkdir()
    capture_path = tmp_path / "uv-command.json"
    uv_path = bin_directory / "uv"
    uv_path.write_text(
        f"#!{sys.executable}\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "with open(os.environ['UV_CAPTURE_PATH'], 'w') as capture:\n"
        "    json.dump({'argv': sys.argv[1:], 'cwd': os.getcwd()}, capture)\n"
    )
    uv_path.chmod(0o700)
    return bin_directory, capture_path


@pytest.fixture(autouse=True)
def tmp_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(str(tmp_path))
    yield


@pytest.fixture
async def process_work_pool(session: AsyncSession):
    job_template = ProcessWorker.get_default_base_job_template()

    wp = await models.workers.create_work_pool(
        session=session,
        work_pool=WorkPoolCreate.model_construct(
            _fields_set=WorkPoolCreate.model_fields_set,
            name="test-worker-pool",
            type="test",
            description="None",
            base_job_template=job_template,
        ),
    )
    await session.commit()
    return wp


@pytest.fixture
async def work_pool_with_default_env(session: AsyncSession):
    job_template = ProcessWorker.get_default_base_job_template()
    job_template["variables"]["properties"]["env"]["default"] = {
        "CONFIG_ENV_VAR": "from_job_configuration"
    }
    wp = await models.workers.create_work_pool(
        session=session,
        work_pool=WorkPoolCreate.model_construct(
            _fields_set=WorkPoolCreate.model_fields_set,
            name="wp-1",
            type="test",
            description="None",
            base_job_template=job_template,
        ),
    )
    await session.commit()
    return wp


async def test_worker_process_run_flow_run(
    flow_run: FlowRun,
    process_work_pool: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
    prefect_client: PrefectClient,
):
    async with ProcessWorker(
        work_pool_name=process_work_pool.name,
    ) as worker:
        result = await worker.run(
            flow_run,
            configuration=await worker.job_configuration.resolve_for_flow_run(
                flow_run,
                client=worker.client,
                work_pool=worker.work_pool,
                worker_name=worker.name,
                worker_id=worker.backend_id,
            ),
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state is not None
        assert flow_run.state.type == StateType.COMPLETED


async def test_process_worker_preserves_handled_failed_outcome(
    prefect_client: PrefectClient,
    process_work_pool: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    flow_id = await prefect_client.create_flow(flow=example_process_worker_flow)
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name=f"test-process-worker-failed-deployment-{uuid.uuid4()}",
        path=str(
            prefect.__development_base_path__
            / "tests"
            / "test-projects"
            / "import-project"
        ),
        entrypoint="my_module/flow.py:failed_flow",
    )
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id,
        state=State(
            type=client_schemas.StateType.SCHEDULED,
            state_details=client_schemas.StateDetails(
                scheduled_time=now("UTC") - timedelta(minutes=5)
            ),
        ),
    )
    crash_marker = tmp_path / "crash-hook-ran"
    monkeypatch.setenv("PREFECT_TEST_PROCESS_WORKER_CRASH_MARKER", str(crash_marker))

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        result = await worker._submit_run_and_capture_errors(flow_run)

    assert isinstance(result, ProcessWorkerResult)
    assert result.status_code == 0
    flow_run = await prefect_client.read_flow_run(flow_run.id)
    assert flow_run.state is not None
    assert flow_run.state.is_failed()
    assert not crash_marker.exists()


async def test_worker_process_run_flow_run_with_env_variables_job_config_defaults(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    work_pool_with_default_env: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EXISTING_ENV_VAR", "from_os")

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        assert configuration.working_dir is None, (
            "This test assumes no configured working_dir"
        )
        result = await worker.run(
            flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

    call_kwargs = mock_workspace_starter.call_args.kwargs

    # should always execute in a tmp directory if working_dir not provided
    workspace_root = call_kwargs.pop("workspace_root")
    source_cwd = call_kwargs.pop("source_cwd")
    assert "tmp" in str(workspace_root)
    assert source_cwd == workspace_root
    assert call_kwargs == {
        "command": None,
        "environment": configuration.env,
        "stream_output": configuration.stream_output,
        "control_channel": ANY,
    }

    assert configuration.env["CONFIG_ENV_VAR"] == "from_job_configuration"
    assert configuration.env["EXISTING_ENV_VAR"] == "from_os"


async def test_worker_process_run_flow_run_with_env_variables_from_overrides(
    flow_run_with_deployment_overrides: FlowRun,
    mock_engine_starter: MagicMock,
    mock_workspace_starter: MagicMock,
    work_pool_with_default_env: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("EXISTING_ENV_VAR", "from_os")

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run_with_deployment_overrides,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        result = await worker.run(
            flow_run_with_deployment_overrides,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

    resolved_working_dir = configuration.working_dir.resolve()
    mock_workspace_starter.assert_not_called()
    mock_engine_starter.assert_called_once_with(
        command=configuration.command,
        cwd=resolved_working_dir,
        env=configuration.env,
        stream_output=configuration.stream_output,
        control_channel=mock_engine_starter.call_args.kwargs["control_channel"],
    )
    assert configuration.env["NEW_ENV_VAR"] == "from_deployment"
    assert configuration.env["EXISTING_ENV_VAR"] == "from_os"


async def test_flow_run_without_job_vars(
    flow_run_with_deployment_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    prefect_client: PrefectClient,
):
    assert flow_run_with_deployment_overrides.deployment_id is not None
    deployment = await prefect_client.read_deployment(
        flow_run_with_deployment_overrides.deployment_id
    )

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run_with_deployment_overrides,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        assert str(configuration.working_dir) == deployment.job_variables["working_dir"]


async def test_flow_run_vars_take_precedence(
    flow_run_with_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    session: AsyncSession,
):
    assert flow_run_with_overrides.deployment_id is not None
    assert flow_run_with_overrides.job_variables is not None
    await models.deployments.update_deployment(
        session=session,
        deployment_id=flow_run_with_overrides.deployment_id,
        deployment=DeploymentUpdate(
            job_variables={"working_dir": "/deployment/tmp/test"},
        ),
    )
    await session.commit()

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        config = await worker.job_configuration.resolve_for_flow_run(
            flow_run_with_overrides,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        assert (
            str(config.working_dir)
            == flow_run_with_overrides.job_variables["working_dir"]
        )


async def test_flow_run_vars_and_deployment_vars_get_merged(
    flow_run_with_overrides: FlowRun,
    work_pool_with_default_env: WorkPool,
    session: AsyncSession,
):
    assert flow_run_with_overrides.deployment_id is not None
    assert flow_run_with_overrides.job_variables is not None
    await models.deployments.update_deployment(
        session=session,
        deployment_id=flow_run_with_overrides.deployment_id,
        deployment=DeploymentUpdate(
            job_variables={"stream_output": False},
        ),
    )
    await session.commit()

    async with ProcessWorker(
        work_pool_name=work_pool_with_default_env.name,
    ) as worker:
        config = await worker.job_configuration.resolve_for_flow_run(
            flow_run_with_overrides,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        assert (
            str(config.working_dir)
            == flow_run_with_overrides.job_variables["working_dir"]
        )
        assert config.stream_output is False


async def test_process_worker_working_dir_override(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
):
    path_override_value = "/tmp/test"

    # Check default is not the mock_path
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_workspace_starter.call_args.kwargs["workspace_root"] != Path(
            path_override_value
        )

    assert flow_run.deployment_id is not None
    # Check mock_path is used after setting the override
    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=client_schemas.actions.DeploymentUpdate(
            job_variables={"working_dir": path_override_value},
        ),
    )
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert (
            mock_workspace_starter.call_args.kwargs["workspace_root"]
            == Path(path_override_value).resolve()
        )


@pytest.fixture
def uv_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A project directory that satisfies every auto-`uv run` condition."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\n"
        "name = 'test-project'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
    monkeypatch.setattr(
        "prefect.runner._uv_command.shutil.which",
        lambda executable, path=None: "/opt/bin/uv" if executable == "uv" else None,
    )
    return tmp_path


@pytest.fixture
def pulled_uv_project(tmp_path: Path) -> Path:
    source_repo = tmp_path / "source-repo"
    flow_file = source_repo / "flows" / "hello.py"
    flow_file.parent.mkdir(parents=True)
    flow_file.write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    return 'hello'\n"
    )
    source_repo.joinpath("pyproject.toml").write_text(
        "[project]\n"
        "name = 'process-worker-pull-test'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )
    subprocess.run(["git", "init"], cwd=source_repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "process-worker@example.com"],
        cwd=source_repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Process Worker"],
        cwd=source_repo,
        check=True,
    )
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=source_repo, check=True)
    return source_repo


async def run_flow_run_with_job_variables(
    flow_run: FlowRun,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    job_variables: dict[str, Any],
) -> None:
    assert flow_run.deployment_id is not None
    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=client_schemas.actions.DeploymentUpdate(
            job_variables=job_variables,
        ),
    )
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        await worker.run(flow_run=flow_run, configuration=configuration)


async def test_process_worker_uses_auto_uv_command_for_project_working_dir(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    uv_project: Path,
):
    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        await run_flow_run_with_job_variables(
            flow_run,
            process_work_pool,
            prefect_client,
            {"working_dir": str(uv_project)},
        )

    assert mock_workspace_starter.call_args.kwargs["command"] is None
    assert mock_workspace_starter.call_args.kwargs["workspace_root"] == uv_project


async def test_process_worker_auto_uv_command_uses_absolute_project_path(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    monkeypatch: pytest.MonkeyPatch,
    uv_project: Path,
):
    # `uv` resolves `--project` relative to the flow run's working directory, so a
    # relative working directory must still produce an absolute project path
    monkeypatch.chdir(uv_project.parent)

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        await run_flow_run_with_job_variables(
            flow_run,
            process_work_pool,
            prefect_client,
            {"working_dir": uv_project.name},
        )

    assert mock_workspace_starter.call_args.kwargs["workspace_root"] == uv_project


async def test_process_worker_preserves_explicitly_configured_engine_command(
    flow_run: FlowRun,
    mock_engine_starter: MagicMock,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    uv_project: Path,
):
    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        await run_flow_run_with_job_variables(
            flow_run,
            process_work_pool,
            prefect_client,
            {
                "working_dir": str(uv_project),
                "command": "python -m prefect.engine",
            },
        )

    mock_workspace_starter.assert_not_called()
    assert mock_engine_starter.call_args.kwargs["command"] == (
        "python -m prefect.engine"
    )


async def test_process_worker_auto_uv_command_honors_job_variable_env(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    uv_project: Path,
):
    # The worker process itself does not have auto-install enabled
    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: False}):
        await run_flow_run_with_job_variables(
            flow_run,
            process_work_pool,
            prefect_client,
            {
                "working_dir": str(uv_project),
                "env": {"PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true"},
            },
        )

    assert (
        mock_workspace_starter.call_args.kwargs["environment"][
            "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES"
        ]
        == "true"
    )


async def test_process_worker_resolves_auto_uv_after_git_clone(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    pulled_uv_project: Path,
    fake_uv: tuple[Path, Path],
):
    bin_directory, capture_path = fake_uv
    flow_id = await prefect_client.create_flow_from_name("pulled-auto-uv")
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name="pulled-auto-uv",
        entrypoint="flows/hello.py:hello",
        pull_steps=[
            {
                "prefect.deployments.steps.git_clone": {
                    "repository": pulled_uv_project.as_uri(),
                    "clone_directory_name": "checkout",
                }
            }
        ],
        job_variables={
            "env": {
                "PATH": os.pathsep.join(
                    [str(bin_directory), os.environ.get("PATH", "")]
                ),
                "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true",
                "UV_CAPTURE_PATH": str(capture_path),
            }
        },
    )
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id,
        state=State(type=client_schemas.StateType.SCHEDULED),
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: False}):
        async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
            configuration = await worker.job_configuration.resolve_for_flow_run(
                flow_run,
                client=worker.client,
                work_pool=worker.work_pool,
                worker_name=worker.name,
                worker_id=worker.backend_id,
            )
            await worker.run(flow_run=flow_run, configuration=configuration)

    captured = json.loads(capture_path.read_text())
    checkout = Path(captured["cwd"])
    assert checkout.name == "checkout"
    assert captured["argv"] == [
        "run",
        "--no-default-groups",
        "--project",
        str(checkout),
        str(
            Path(_workspace_starter.__file__).with_name(
                "_workspace_runtime_bootstrap.py"
            )
        ),
        "engine",
        "flows/hello.py:hello",
    ]


async def test_process_worker_resolves_auto_uv_for_preexisting_project(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    tmp_path: Path,
    fake_uv: tuple[Path, Path],
):
    bin_directory, capture_path = fake_uv
    project = tmp_path / "preexisting-project"
    flow_file = project / "flows" / "hello.py"
    flow_file.parent.mkdir(parents=True)
    flow_file.write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    return 'hello'\n"
    )
    project.joinpath("pyproject.toml").write_text(
        "[project]\n"
        "name = 'preexisting-process-worker-test'\n"
        "version = '0.1.0'\n"
        "dependencies = ['prefect']\n"
    )

    flow_id = await prefect_client.create_flow_from_name("preexisting-auto-uv")
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name="preexisting-auto-uv",
        path=str(project),
        entrypoint="flows/hello.py:hello",
        job_variables={
            "working_dir": str(project),
            "env": {
                "PATH": os.pathsep.join(
                    [str(bin_directory), os.environ.get("PATH", "")]
                ),
                "PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES": "true",
                "UV_CAPTURE_PATH": str(capture_path),
            },
        },
    )
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id,
        state=State(type=client_schemas.StateType.SCHEDULED),
    )

    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: False}):
        async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
            configuration = await worker.job_configuration.resolve_for_flow_run(
                flow_run,
                client=worker.client,
                work_pool=worker.work_pool,
                worker_name=worker.name,
                worker_id=worker.backend_id,
            )
            await worker.run(flow_run=flow_run, configuration=configuration)

    captured = json.loads(capture_path.read_text())
    assert Path(captured["cwd"]) == project
    assert captured["argv"] == [
        "run",
        "--no-default-groups",
        "--project",
        str(project),
        str(
            Path(_workspace_starter.__file__).with_name(
                "_workspace_runtime_bootstrap.py"
            )
        ),
        "engine",
        "flows/hello.py:hello",
    ]


async def test_process_worker_keeps_engine_command_without_project(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
):
    with temporary_settings({PREFECT_RUNNER_AUTO_INSTALL_DEPENDENCIES: True}):
        async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
            configuration = await worker.job_configuration.resolve_for_flow_run(
                flow_run,
                client=worker.client,
                work_pool=worker.work_pool,
                worker_name=worker.name,
                worker_id=worker.backend_id,
            )
            await worker.run(flow_run=flow_run, configuration=configuration)

    assert mock_workspace_starter.call_args.kwargs["command"] is None


async def test_process_worker_stream_output_override(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
):
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_workspace_starter.call_args.kwargs["stream_output"] is True

    assert flow_run.deployment_id is not None
    await prefect_client.update_deployment(
        deployment_id=flow_run.deployment_id,
        deployment=client_schemas.actions.DeploymentUpdate(
            job_variables={"stream_output": False},
        ),
    )

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        assert mock_workspace_starter.call_args.kwargs["stream_output"] is False


async def test_process_worker_leaves_pull_steps_to_explicit_command(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    output_marker = "PULL_STEP_MUST_NOT_RUN_IN_WORKER"
    project = tmp_path / "quiet-project"
    project.mkdir()
    project.joinpath("flow.py").write_text(
        "from prefect import flow\n\n@flow\ndef hello():\n    pass\n"
    )
    flow_id = await prefect_client.create_flow_from_name("quiet-pull-step")
    deployment_id = await prefect_client.create_deployment(
        flow_id=flow_id,
        name="quiet-pull-step",
        entrypoint="flow.py:hello",
        pull_steps=[
            {
                "prefect.deployments.steps.run_shell_script": {
                    "script": command_to_string(
                        [sys.executable, "-c", f"print({output_marker!r})"]
                    )
                }
            }
        ],
        job_variables={
            "working_dir": str(project),
            "command": command_to_string([sys.executable, "-c", "pass"]),
            "stream_output": True,
        },
    )
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment_id,
        state=State(type=client_schemas.StateType.SCHEDULED),
    )

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        await worker.run(flow_run=flow_run, configuration=configuration)

    captured = capfd.readouterr()
    assert output_marker not in captured.out
    assert output_marker not in captured.err


async def test_process_worker_executes_flow_run_with_workspace_starter(
    flow_run: FlowRun,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
):
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        assert configuration.working_dir is None, (
            "This test assumes no configured working_dir"
        )
        result = await worker.run(
            flow_run=flow_run,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0

        call_kwargs = mock_workspace_starter.call_args.kwargs

        # should always execute in a tmp directory if working_dir not provided
        workspace_root = call_kwargs.pop("workspace_root")
        source_cwd = call_kwargs.pop("source_cwd")
        assert "tmp" in str(workspace_root)
        assert source_cwd == workspace_root
        assert call_kwargs == {
            "command": None,
            "environment": configuration.env,
            "stream_output": configuration.stream_output,
            "control_channel": ANY,
        }


async def test_process_worker_command_override(
    deployment_with_overrides: Deployment,
    flow_run_with_deployment_overrides: FlowRun,
    mock_engine_starter: MagicMock,
    mock_workspace_starter: MagicMock,
    process_work_pool: WorkPool,
    monkeypatch: pytest.MonkeyPatch,
):
    override_command = deployment_with_overrides.job_variables["command"]
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        configuration = await worker.job_configuration.resolve_for_flow_run(
            flow_run_with_deployment_overrides,
            client=worker.client,
            work_pool=worker.work_pool,
            worker_name=worker.name,
            worker_id=worker.backend_id,
        )
        result = await worker.run(
            flow_run=flow_run_with_deployment_overrides,
            configuration=configuration,
        )

        assert isinstance(result, ProcessWorkerResult)
        assert result.status_code == 0
        resolved_working_dir = configuration.working_dir.resolve()
        mock_workspace_starter.assert_not_called()
        mock_engine_starter.assert_called_once_with(
            command=override_command,
            cwd=resolved_working_dir,
            env=configuration.env,
            stream_output=configuration.stream_output,
            control_channel=mock_engine_starter.call_args.kwargs["control_channel"],
        )


async def test_task_status_receives_pid(
    process_work_pool: WorkPool,
    flow_run: FlowRun,
):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        result = await worker.run(
            flow_run=flow_run,
            configuration=await worker.job_configuration.resolve_for_flow_run(
                flow_run,
                client=worker.client,
                work_pool=worker.work_pool,
                worker_name=worker.name,
                worker_id=worker.backend_id,
            ),
            task_status=fake_status,
        )

        fake_status.started.assert_called_once_with(int(result.identifier))


async def test_submit_adhoc_run_with_existing_flow_run_reuses_id(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that _submit_adhoc_run with flow_run parameter reuses the flow run ID."""
    # Mock execute_bundle to prevent actual execution
    mock_execute_bundle = AsyncMock()
    monkeypatch.setattr(
        "prefect.runner.runner.Runner.execute_bundle", mock_execute_bundle
    )

    @flow
    def test_flow():
        return "success"

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        # Create an initial flow run
        initial_flow_run = await prefect_client.create_flow_run(
            test_flow,
            parameters={},
            state=client_schemas.State(type=client_schemas.StateType.FAILED),
        )

        # Call _submit_adhoc_run with the existing flow run to retry it
        await worker._submit_adhoc_run(
            flow=test_flow,
            parameters={},
            flow_run=initial_flow_run,
        )

        # The flow run should have been reused (same ID) and state set to Pending
        retried_flow_run = await prefect_client.read_flow_run(initial_flow_run.id)

        # State should be Pending (set before retry execution)
        assert retried_flow_run.state is not None
        assert retried_flow_run.state.type == client_schemas.StateType.PENDING


async def test_submit_adhoc_run_with_existing_flow_run_sets_pending_state(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that _submit_adhoc_run sets the state to Pending when retrying."""
    # Mock execute_bundle to prevent actual execution
    mock_execute_bundle = AsyncMock()
    monkeypatch.setattr(
        "prefect.runner.runner.Runner.execute_bundle", mock_execute_bundle
    )

    @flow
    def test_flow():
        return "done"

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        # Create an initial flow run with FAILED state
        initial_flow_run = await prefect_client.create_flow_run(
            test_flow,
            parameters={},
            state=client_schemas.State(type=client_schemas.StateType.FAILED),
        )

        # Verify initial state is FAILED
        assert initial_flow_run.state is not None
        assert initial_flow_run.state.type == client_schemas.StateType.FAILED

        # Call _submit_adhoc_run with the existing flow run
        await worker._submit_adhoc_run(
            flow=test_flow,
            parameters={},
            flow_run=initial_flow_run,
        )

        # execute_bundle should have been called (which means state was set to Pending first)
        mock_execute_bundle.assert_called()

        # Verify the flow run state was set to Pending before execution
        retried_flow_run = await prefect_client.read_flow_run(initial_flow_run.id)
        # The state should have been set to Pending (or a subsequent state after execution)
        # Since we mocked execute_bundle, the state should still be Pending
        assert retried_flow_run.state is not None
        assert retried_flow_run.state.type == client_schemas.StateType.PENDING


async def test_submit_adhoc_run_without_flow_run_creates_new_run(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that _submit_adhoc_run creates a new flow run when flow_run is None."""
    # Mock execute_bundle to prevent actual execution
    mock_execute_bundle = AsyncMock()
    monkeypatch.setattr(
        "prefect.runner.runner.Runner.execute_bundle", mock_execute_bundle
    )

    @flow
    def test_flow():
        return "new run"

    # Get initial count of flow runs
    initial_flow_runs = await prefect_client.read_flow_runs()
    initial_count = len(initial_flow_runs)

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        # Call _submit_adhoc_run without flow_run parameter
        await worker._submit_adhoc_run(
            flow=test_flow,
            parameters={},
        )

    # A new flow run should have been created
    final_flow_runs = await prefect_client.read_flow_runs()
    assert len(final_flow_runs) > initial_count


async def test_submit_adhoc_run_crashes_when_bundle_creation_fails(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    tmp_path: Path,
):
    @flow
    def test_flow() -> None:
        pass

    bound_flow = bind_flow_to_infrastructure(
        flow=test_flow,
        work_pool=process_work_pool.name,
        worker_cls=ProcessWorker,
        include_files=["config.yaml"],
        include_files_base_dir=tmp_path / "missing",
    )
    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        with pytest.warns(FutureWarning):
            future = await worker.submit(bound_flow)

    flow_run = await prefect_client.read_flow_run(future.flow_run_id)
    assert flow_run.state is not None
    assert flow_run.state.is_crashed()
    assert flow_run.state.message is not None
    assert "include_files_base_dir" in flow_run.state.message


async def test_submit_adhoc_run_passes_worker_id_for_attribution(
    process_work_pool: WorkPool,
    prefect_client: PrefectClient,
    monkeypatch: pytest.MonkeyPatch,
):
    """_submit_adhoc_run should pass worker_id to prepare_for_flow_run for attribution."""
    mock_execute_bundle = AsyncMock()
    monkeypatch.setattr(
        "prefect.runner.runner.Runner.execute_bundle", mock_execute_bundle
    )

    @flow
    def test_flow():
        return "attribution"

    async with ProcessWorker(work_pool_name=process_work_pool.name) as worker:
        worker.backend_id = uuid.uuid4()

        from prefect.workers.process import ProcessJobConfiguration

        original_prepare = ProcessJobConfiguration.prepare_for_flow_run
        prepare_calls: list[dict] = []

        def tracking_prepare(self, flow_run, **kwargs):
            prepare_calls.append(kwargs)
            return original_prepare(self, flow_run, **kwargs)

        monkeypatch.setattr(
            ProcessJobConfiguration, "prepare_for_flow_run", tracking_prepare
        )

        await worker._submit_adhoc_run(
            flow=test_flow,
            parameters={},
        )

    assert len(prepare_calls) == 1
    assert prepare_calls[0]["worker_id"] == worker.backend_id
    assert prepare_calls[0]["worker_name"] == worker.name
