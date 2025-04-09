import uuid
import warnings
from typing import Any, Callable, Generator, Union
from unittest import mock

import httpx
import pytest

from prefect import flow
from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.client.schemas.objects import FlowRun
from prefect.runner import submit_to_runner
from prefect.settings import (
    PREFECT_RUNNER_SERVER_ENABLE,
    temporary_settings,
)
from prefect.states import Running


@flow
def identity(whatever: Any):
    return whatever


@flow
async def async_identity(whatever: Any):
    return whatever


@flow
def super_identity(*args: Any, **kwargs: Any):
    return args, kwargs


@flow(log_prints=True)
def independent():
    print("i don't need no stinkin' parameters")


@pytest.fixture
def mock_webserver(monkeypatch: pytest.MonkeyPatch):
    async def mock_submit_flow_to_runner(_: Any, parameters: Any, *__: Any) -> FlowRun:
        return FlowRun(flow_id=uuid.uuid4(), state=Running(), parameters=parameters)

    monkeypatch.setattr(
        "prefect.runner.submit._submit_flow_to_runner", mock_submit_flow_to_runner
    )


@pytest.fixture
def mock_webserver_not_running(monkeypatch: pytest.MonkeyPatch):
    async def mock_submit_flow_to_runner(*_: Any, **__: Any):
        raise httpx.ConnectError("Mocked connection error")

    monkeypatch.setattr(
        "prefect.runner.submit._submit_flow_to_runner", mock_submit_flow_to_runner
    )


@pytest.fixture(autouse=True)
def runner_settings() -> Generator[None, None, None]:
    with temporary_settings({PREFECT_RUNNER_SERVER_ENABLE: True}):
        yield


@pytest.fixture(autouse=True)
def suppress_deprecation_warning() -> Generator[None, None, None]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PrefectDeprecationWarning)
        yield


@pytest.mark.parametrize("prefect_callable", [identity, async_identity])
@pytest.mark.usefixtures("mock_webserver")
def test_submit_to_runner_happy_path_sync_context(prefect_callable: Callable[..., Any]):
    @flow
    def test_flow() -> FlowRun:
        return submit_to_runner(prefect_callable, {"whatever": 42})

    flow_run = test_flow()
    assert flow_run.state is not None
    assert flow_run.state.is_running()
    assert flow_run.parameters == {"whatever": 42}


@pytest.mark.parametrize("prefect_callable", [identity, async_identity])
@pytest.mark.usefixtures("mock_webserver")
async def test_submit_to_runner_happy_path_async_context(
    prefect_callable: Callable[..., Any],
):
    flow_run = await submit_to_runner(prefect_callable, {"whatever": 42})

    assert flow_run.state.is_running()
    assert flow_run.parameters == {"whatever": 42}


async def test_submit_to_runner_raises_if_not_prefect_callable():
    with pytest.raises(
        TypeError,
        match=(
            "The `submit_to_runner` utility only supports submitting flows and tasks."
        ),
    ):
        await submit_to_runner(lambda: None)


@pytest.mark.usefixtures("mock_webserver")
async def test_submission_with_optional_parameters():
    flow_run = await submit_to_runner(independent)

    assert flow_run.state.is_running()
    assert flow_run.parameters == {}


@pytest.mark.usefixtures("mock_webserver_not_running")
async def test_submission_raises_if_webserver_not_running():
    with temporary_settings({PREFECT_RUNNER_SERVER_ENABLE: False}):
        with pytest.raises(
            (httpx.ConnectTimeout, RuntimeError),
            match="Ensure that the server is running",
        ):
            await submit_to_runner(identity, {"d": {"input": 9001}})


@pytest.mark.parametrize("input_", [[{"input": 1}, {"input": 2}], {"input": 3}])
@pytest.mark.usefixtures("mock_webserver")
async def test_return_for_submissions_matches_input(
    input_: Union[list[dict[str, Any]], dict[str, Any]],
):
    def _flow_run_generator(*_: Any, **__: Any) -> FlowRun:
        return FlowRun(flow_id=uuid.uuid4())

    with mock.patch(
        "prefect.runner.submit._submit_flow_to_runner",
        side_effect=_flow_run_generator,
    ):
        results = await submit_to_runner(identity, input_)

        if isinstance(input_, dict):
            assert isinstance(results, FlowRun)
        else:
            assert len(results) == len(input_)
            assert all(isinstance(r, FlowRun) for r in results)


@pytest.mark.parametrize(
    "input_",
    [
        {
            "name": "Schleeb",
            "age": 99,
            "young": True,
            "metadata": [{"nested": "info"}],
            "data": [True, False, True],
            "info": {"nested": "info"},
        },
        [
            {
                "name": "Schleeb",
                "age": 99,
                "young": True,
                "metadata": [{"nested": "info"}],
                "data": [True, False, True],
                "info": {"nested": "info"},
            }
        ],
        [
            {
                "name": "Schleeb",
                "age": 99,
                "young": True,
                "metadata": [{"nested": "info"}],
                "data": [True, False, True],
                "info": {"nested": "info"},
            }
        ],
        [{"1": {2: {3: {4: None}}}}],
    ],
)
@pytest.mark.usefixtures("mock_webserver")
async def test_types_in_submission(
    input_: Union[list[dict[str, Any]], dict[str, Any]],
):
    results = await submit_to_runner(super_identity, input_)

    if isinstance(input_, list):
        assert len(results) == len(input_)
        for r in results:
            assert isinstance(r, FlowRun)
    else:
        assert isinstance(results, FlowRun)
