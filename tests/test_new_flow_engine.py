import logging
from uuid import UUID

import pytest

from prefect import Flow, flow, get_run_logger
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import StateType
from prefect.context import FlowRunContext
from prefect.new_flow_engine import FlowRunEngine, run_flow
from prefect.settings import PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE, temporary_settings
from prefect.utilities.callables import get_call_parameters


@pytest.fixture(autouse=True)
def set_new_engine_setting():
    with temporary_settings({PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE: True}):
        yield


@flow
async def foo():
    return 42


async def test_setting_is_set():
    assert PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE.value() is True


class TestFlowRunEngine:
    async def test_basic_init(self):
        engine = FlowRunEngine(flow=foo)
        assert isinstance(engine.flow, Flow)
        assert engine.flow.name == "foo"
        assert engine.parameters == {}

    async def test_get_client_raises_informative_error(self):
        engine = FlowRunEngine(flow=foo)
        with pytest.raises(RuntimeError, match="not started"):
            await engine.get_client()

    async def test_get_client_returns_client_after_starting(self):
        engine = FlowRunEngine(flow=foo)
        async with engine.start():
            client = await engine.get_client()
            assert isinstance(client, PrefectClient)

        with pytest.raises(RuntimeError, match="not started"):
            await engine.get_client()


class TestFlowRuns:
    async def test_basic(self):
        @flow
        async def foo():
            return 42

        result = await run_flow(foo)

        assert result == 42

    async def test_with_params(self):
        @flow
        async def bar(x: int, y: str = None):
            return x, y

        parameters = get_call_parameters(bar.fn, (42,), dict(y="nate"))
        result = await run_flow(bar, parameters=parameters)

        assert result == (42, "nate")

    async def test_flow_run_name(self, prefect_client):
        @flow(flow_run_name="name is {x}")
        async def foo(x):
            return FlowRunContext.get().flow_run.id

        result = await run_flow(foo, parameters=dict(x="blue"))
        run = await prefect_client.read_flow_run(result)

        assert run.name == "name is blue"

    async def test_get_run_logger(self, caplog):
        caplog.set_level(logging.CRITICAL)

        @flow(flow_run_name="test-run")
        async def my_log_flow():
            get_run_logger().critical("hey yall")

        result = await run_flow(my_log_flow)

        assert result is None
        record = caplog.records[0]

        assert record.flow_name == "my-log-flow"
        assert record.flow_run_name == "test-run"
        assert UUID(record.flow_run_id)
        assert record.message == "hey yall"
        assert record.levelname == "CRITICAL"

    async def test_flow_ends_in_completed(self, prefect_client):
        @flow
        async def foo():
            return FlowRunContext.get().flow_run.id

        result = await run_flow(foo)
        run = await prefect_client.read_flow_run(result)

        assert run.state_type == StateType.COMPLETED

    async def test_flow_ends_in_failed(self, prefect_client):
        ID = None

        @flow
        async def foo():
            nonlocal ID
            ID = FlowRunContext.get().flow_run.id
            raise ValueError("xyz")

        with pytest.raises(ValueError, match="xyz"):
            await run_flow(foo)

        run = await prefect_client.read_flow_run(ID)

        assert run.state_type == StateType.FAILED

    @pytest.mark.skip(reason="Havent wired up subflows yet")
    async def test_flow_tracks_nested_parent_as_dependency(self, prefect_client):
        @flow
        async def inner():
            return FlowRunContext.get().flow_run.id

        @flow
        async def outer():
            id1 = await inner()
            return (id1, FlowRunContext.get().flow_run.id)

        a, b = await run_flow(outer)
        assert a != b

        # assertions on outer
        outer_run = await prefect_client.read_flow_run(b)
        assert outer_run.flow_inputs == {}

        # assertions on inner
        inner_run = await prefect_client.read_flow_run(a)
        assert "wait_for" in inner_run.flow_inputs
        assert inner_run.flow_inputs["wait_for"][0].id == b
