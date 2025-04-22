import asyncio
import sys
import uuid
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_docker.experimental.decorators import docker
from prefect_docker.worker import DockerWorker

import prefect
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.client.schemas.objects import (
    WorkPool,
    WorkPoolStorageConfiguration,
)
from prefect.futures import PrefectFuture


@pytest.fixture
def mock_submit(monkeypatch: pytest.MonkeyPatch) -> Generator[AsyncMock, None, None]:
    """Create a mock for the DockerWorker.submit method"""
    # Create a mock state
    mock_state = MagicMock(spec=prefect.State)
    mock_state.is_completed.return_value = True
    mock_state.message = "Success"

    # Create a mock future
    mock_future = MagicMock(spec=PrefectFuture)
    mock_future.aresult = AsyncMock(return_value="test_result")
    mock_future.wait_async = AsyncMock()
    mock_future.state = mock_state

    mock = AsyncMock(return_value=mock_future)

    monkeypatch.setattr(DockerWorker, "submit", mock)
    yield mock


@pytest.fixture
def mock_run(monkeypatch: pytest.MonkeyPatch) -> Generator[AsyncMock, None, None]:
    mock = AsyncMock()
    mock.return_value = MagicMock(status_code=0)
    monkeypatch.setattr(DockerWorker, "run", mock)
    yield mock


@pytest.fixture
async def work_pool_without_storage_configuration():
    async with prefect.get_client() as client:
        work_pool = await client.create_work_pool(
            WorkPoolCreate(
                name=f"test-{uuid.uuid4()}",
                base_job_template=DockerWorker.get_default_base_job_template(),
            )
        )
        try:
            yield work_pool
        finally:
            await client.delete_work_pool(work_pool.name)


@pytest.fixture
async def work_pool_with_storage_configuration():
    UPLOAD_STEP = {
        "prefect_mock.experimental.bundles.upload": {
            "requires": "prefect-mock==0.5.5",
            "bucket": "test-bucket",
            "credentials_block_name": "my-creds",
        }
    }

    EXECUTE_STEP = {
        "prefect_mock.experimental.bundles.execute": {
            "requires": "prefect-mock==0.5.5",
            "bucket": "test-bucket",
            "credentials_block_name": "my-creds",
        }
    }

    async with prefect.get_client() as client:
        work_pool = await client.create_work_pool(
            WorkPoolCreate(
                name=f"test-{uuid.uuid4()}",
                base_job_template=DockerWorker.get_default_base_job_template(),
                storage_configuration=WorkPoolStorageConfiguration(
                    bundle_execution_step=EXECUTE_STEP,
                    bundle_upload_step=UPLOAD_STEP,
                ),
            )
        )
        try:
            yield work_pool
        finally:
            await client.delete_work_pool(work_pool.name)


def test_docker_decorator_sync_flow(mock_submit: AsyncMock) -> None:
    """Test that a synchronous flow is correctly decorated and executed"""

    @docker(work_pool="test-pool", volumes=["/tmp/test:/tmp/test"])
    @prefect.flow
    def sync_test_flow(param1: str, param2: str = "default") -> str:
        return f"{param1}-{param2}"

    result = sync_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert kwargs["parameters"] == {"param1": "test", "param2": "default"}
    assert kwargs["job_variables"] == {"volumes": ["/tmp/test:/tmp/test"]}
    assert result == "test_result"


async def test_docker_decorator_async_flow(mock_submit: AsyncMock) -> None:
    """Test that an asynchronous flow is correctly decorated and executed"""

    @docker(work_pool="test-pool", volumes=["/tmp/test:/tmp/test"])
    @prefect.flow
    async def async_test_flow(param1: str) -> str:
        return f"async-{param1}"

    result = await async_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert kwargs["parameters"] == {"param1": "test"}
    assert kwargs["job_variables"] == {"volumes": ["/tmp/test:/tmp/test"]}
    assert result == "test_result"


@pytest.mark.usefixtures("mock_submit")
def test_docker_decorator_return_state() -> None:
    """Test that return_state=True returns the state instead of the result"""

    @docker(work_pool="test-pool")
    @prefect.flow
    def test_flow():
        return "completed"

    state = test_flow(return_state=True)

    assert state.is_completed()
    assert state.message == "Success"


@pytest.mark.usefixtures("mock_submit")
def test_docker_decorator_preserves_flow_attributes() -> None:
    """Test that the decorator preserves the original flow's attributes"""

    @prefect.flow(name="custom-flow-name", description="Custom description")
    def original_flow():
        return "test"

    original_name = original_flow.name
    original_description = original_flow.description

    decorated_flow = docker(work_pool="test-pool")(original_flow)

    assert decorated_flow.name == original_name
    assert decorated_flow.description == original_description

    result = decorated_flow()
    assert result == "test_result"


def test_submit_method_receives_work_pool_name(mock_submit: AsyncMock) -> None:
    """Test that the correct work pool name is passed to submit"""

    @docker(work_pool="specific-pool")
    @prefect.flow
    def test_flow():
        return "test"

    test_flow()

    mock_submit.assert_called_once()
    kwargs = mock_submit.call_args.kwargs
    assert "flow" in kwargs
    assert "parameters" in kwargs
    assert "job_variables" in kwargs


async def test_uses_volume_mount_when_work_pool_has_storage_configuration(
    work_pool_without_storage_configuration: WorkPool,
    mock_run: AsyncMock,
) -> None:
    """Test that a volume mount is used when the work pool is missing storage configuration"""

    @prefect.flow
    def test_flow():
        return "test"

    async with DockerWorker(
        work_pool_name=work_pool_without_storage_configuration.name
    ) as worker:
        await worker.submit(
            test_flow, job_variables={"volumes": ["/tmp/test:/tmp/test"]}
        )
        # Small sleep to ensure the run mock is called
        await asyncio.sleep(0.1)

        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        configuration = kwargs["configuration"]
        assert len(configuration.volumes) == 2
        assert configuration.volumes[0] == "/tmp/test:/tmp/test"
        assert configuration.volumes[1].endswith("/tmp/")

        python_version = sys.version_info
        assert configuration.command.startswith(
            f"uv run --with prefect --python {python_version.major}.{python_version.minor} -m prefect._experimental.bundles.execute"
        )
