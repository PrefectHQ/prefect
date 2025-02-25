from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from prefect_kubernetes.experimental.decorators import kubernetes
from prefect_kubernetes.worker import KubernetesWorker

from prefect import State, flow
from prefect.futures import PrefectFuture


@pytest.fixture
def mock_submit() -> Generator[AsyncMock, None, None]:
    """Create a mock for the KubernetesWorker.submit method"""
    # Create a mock state
    mock_state = MagicMock(spec=State)
    mock_state.is_completed.return_value = True
    mock_state.message = "Success"

    # Create a mock future
    mock_future = MagicMock(spec=PrefectFuture)
    mock_future.aresult = AsyncMock(return_value="test_result")
    mock_future.wait_async = AsyncMock()
    mock_future.state = mock_state

    mock = AsyncMock(return_value=mock_future)

    patcher = patch.object(KubernetesWorker, "submit", mock)
    patcher.start()
    yield mock
    patcher.stop()


def test_kubernetes_decorator_sync_flow(mock_submit: AsyncMock) -> None:
    """Test that a synchronous flow is correctly decorated and executed"""

    @kubernetes(work_pool="test-pool", memory="2Gi")
    @flow
    def sync_test_flow(param1, param2="default"):
        return f"{param1}-{param2}"

    result = sync_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert kwargs["parameters"] == {"param1": "test", "param2": "default"}
    assert kwargs["job_variables"] == {"memory": "2Gi"}
    assert result == "test_result"


async def test_kubernetes_decorator_async_flow(mock_submit: AsyncMock) -> None:
    """Test that an asynchronous flow is correctly decorated and executed"""

    @kubernetes(work_pool="test-pool", cpu="1")
    @flow
    async def async_test_flow(param1):
        return f"async-{param1}"

    result = await async_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert kwargs["parameters"] == {"param1": "test"}
    assert kwargs["job_variables"] == {"cpu": "1"}
    assert result == "test_result"


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_return_state() -> None:
    """Test that return_state=True returns the state instead of the result"""

    @kubernetes(work_pool="test-pool")
    @flow
    def test_flow():
        return "completed"

    state = test_flow(return_state=True)

    assert state.is_completed()
    assert state.message == "Success"


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_preserves_flow_attributes() -> None:
    """Test that the decorator preserves the original flow's attributes"""

    @flow(name="custom-flow-name", description="Custom description")
    def original_flow():
        return "test"

    original_name = original_flow.name
    original_description = original_flow.description

    decorated_flow = kubernetes(work_pool="test-pool")(original_flow)

    assert decorated_flow.name == original_name
    assert decorated_flow.description == original_description

    result = decorated_flow()
    assert result == "test_result"


def test_submit_method_receives_work_pool_name(mock_submit: AsyncMock) -> None:
    """Test that the correct work pool name is passed to submit"""

    @kubernetes(work_pool="specific-pool")
    @flow
    def test_flow():
        return "test"

    test_flow()

    mock_submit.assert_called_once()
    kwargs = mock_submit.call_args.kwargs
    assert "flow" in kwargs
    assert "parameters" in kwargs
    assert "job_variables" in kwargs
