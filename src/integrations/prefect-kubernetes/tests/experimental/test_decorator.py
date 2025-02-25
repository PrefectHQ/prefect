from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_kubernetes._decorators import kubernetes
from prefect_kubernetes.worker import KubernetesWorker

from prefect import State, flow
from prefect.futures import PrefectFuture


@pytest.fixture
def mock_submit(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Mock the KubernetesWorker.submit method"""
    # Create a mock state
    mock_state = MagicMock(spec=State)
    mock_state.is_completed.return_value = True
    mock_state.message = "Success"

    # Create a mock future
    mock_future = MagicMock(spec=PrefectFuture)
    mock_future.aresult = AsyncMock(return_value="test_result")
    mock_future.wait_async = AsyncMock()
    mock_future.state = mock_state

    # Create the submit mock
    mock = AsyncMock(return_value=mock_future)

    # Patch just the submit method
    monkeypatch.setattr(KubernetesWorker, "submit", mock)

    # Return the mock so we can make assertions on it
    return mock


def test_kubernetes_decorator_sync_flow(mock_submit: AsyncMock) -> None:
    @kubernetes(work_pool="test-pool", memory="2Gi")
    @flow
    def sync_test_flow(param1, param2="default"):
        return f"{param1}-{param2}"

    result = sync_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert args == ()
    assert kwargs["parameters"] == {"param1": "test", "param2": "default"}
    assert kwargs["job_variables"] == {"memory": "2Gi"}
    assert result == "test_result"


async def test_kubernetes_decorator_async_flow(mock_submit: AsyncMock) -> None:
    @kubernetes(work_pool="test-pool", cpu="1")
    @flow
    async def async_test_flow(param1):
        return f"async-{param1}"

    result = await async_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert args == ()
    assert kwargs["parameters"] == {"param1": "test"}
    assert kwargs["job_variables"] == {"cpu": "1"}
    assert result == "test_result"


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_return_state() -> None:
    @kubernetes(work_pool="test-pool")
    @flow
    def test_flow():
        return "completed"

    state = test_flow(return_state=True)

    assert state.is_completed()
    assert state.message == "Success"


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_preserves_flow_attributes() -> None:
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


@pytest.fixture
def mock_worker_context(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Mock the worker context manager to avoid actual worker creation"""
    # Create a properly structured async worker mock
    worker_mock = AsyncMock()
    worker_mock.__aenter__.return_value = worker_mock
    worker_mock.__aexit__.return_value = None

    # Add the submit method that returns an async result
    mock_future = MagicMock(spec=PrefectFuture)
    mock_future.aresult = AsyncMock(return_value="test_result")
    mock_future.wait_async = AsyncMock()
    mock_future.state = MagicMock(spec=State)
    mock_future.state.is_completed.return_value = True
    mock_future.state.message = "Success"

    worker_mock.submit = AsyncMock(return_value=mock_future)

    # Patch the constructor to track work_pool_name
    original_init = KubernetesWorker.__init__

    def init_wrapper(self, work_pool_name=None, **kwargs: Any):
        self.captured_work_pool_name = work_pool_name
        if original_init != object.__init__:
            original_init(self, work_pool_name=work_pool_name, **kwargs)

    monkeypatch.setattr(KubernetesWorker, "__init__", init_wrapper)
    monkeypatch.setattr(
        KubernetesWorker, "__new__", lambda cls, *args, **kwargs: worker_mock
    )
    return worker_mock


@pytest.mark.usefixtures("mock_submit")
def test_worker_creation(mock_worker_context: AsyncMock) -> None:
    """Test the worker context is properly used"""

    @kubernetes(work_pool="specific-pool")
    @flow
    def test_flow():
        return "test"

    result = test_flow()

    # Verify the result matches what our mock returns
    assert result == "test_result"
    # Verify the worker's submit method was called
    mock_worker_context.submit.assert_called_once()
