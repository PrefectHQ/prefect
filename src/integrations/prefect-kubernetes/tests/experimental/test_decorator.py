from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_kubernetes._decorators import kubernetes
from prefect_kubernetes.worker import KubernetesWorker

from prefect import flow
from prefect.futures import PrefectFuture
from prefect.states import Completed


@pytest.fixture
def mock_submit(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Mock the KubernetesWorker.submit method"""
    mock_future = MagicMock(spec=PrefectFuture)
    mock_future.aresult = AsyncMock(return_value="test_result")
    mock_future.wait_async = AsyncMock()
    mock_future.state = Completed()

    mock = AsyncMock(return_value=mock_future)

    # Patch just the submit method
    monkeypatch.setattr(KubernetesWorker, "submit", mock)

    # Return the mock so we can make assertions on it
    return mock


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_sync_flow(mock_submit: AsyncMock) -> None:
    @kubernetes(work_pool="test-pool", memory="2Gi")
    @flow
    def sync_test_flow(param1: str, param2: str = "default") -> str:
        return f"{param1}-{param2}"

    result = sync_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert args == ()
    assert kwargs["parameters"] == {"param1": "test", "param2": "default"}
    assert kwargs["job_variables"] == {"memory": "2Gi"}
    assert result == "test_result"


@pytest.mark.usefixtures("mock_submit")
async def test_kubernetes_decorator_async_flow(mock_submit: AsyncMock) -> None:
    @kubernetes(work_pool="test-pool", cpu="1")
    @flow
    async def async_test_flow(param1: str) -> str:
        return f"async-{param1}"

    result = await async_test_flow("test")

    mock_submit.assert_called_once()
    args, kwargs = mock_submit.call_args
    assert args == ()
    assert kwargs["parameters"] == {"param1": "test"}
    assert kwargs["job_variables"] == {"cpu": "1"}
    assert result == "test_result"


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_return_state(mock_submit: AsyncMock) -> None:
    @kubernetes(work_pool="test-pool")
    @flow
    def test_flow():
        return "completed"

    state = test_flow(return_state=True)

    assert state.is_completed()
    assert state.message == "Success"


@pytest.mark.usefixtures("mock_submit")
def test_kubernetes_decorator_preserves_flow_attributes(mock_submit: AsyncMock) -> None:
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
def mock_worker_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the worker context manager to avoid actual worker creation"""
    worker_mock = MagicMock()
    worker_mock.__aenter__ = AsyncMock(return_value=worker_mock)
    worker_mock.__aexit__ = AsyncMock(return_value=None)

    monkeypatch.setattr(KubernetesWorker, "__init__", lambda self, work_pool_name: None)
    monkeypatch.setattr(
        KubernetesWorker, "__new__", lambda cls, *args, **kwargs: worker_mock
    )


@pytest.mark.usefixtures("mock_worker_context", "mock_submit")
def test_worker_creation() -> None:
    """Test that the worker is created with the correct work pool name"""

    @kubernetes(work_pool="specific-pool")
    @flow
    def test_flow():
        return "test"

    test_flow()

    # Since we're mocking __new__, we can't easily test the work_pool_name parameter
    # This test primarily ensures the worker context is used correctly
