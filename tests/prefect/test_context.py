import pytest

from uuid import uuid4
from contextvars import ContextVar
from prefect import flow, task
from prefect.context import (
    FlowRunContext,
    TaskRunContext,
    ContextModel,
    RunContext,
)
from prefect.client import OrionClient


class ExampleContext(ContextModel):
    __var__ = ContextVar("test")

    x: int


def test_context_enforces_types():
    with pytest.raises(ValueError):
        ExampleContext(x="hello")


def test_context_get_outside_context_is_null():
    assert ExampleContext.get() is None


def test_context_exit_restores_previous_context():
    with ExampleContext(x=1):
        with ExampleContext(x=2):
            with ExampleContext(x=3):
                assert ExampleContext.get().x == 3
            assert ExampleContext.get().x == 2
        assert ExampleContext.get().x == 1
    assert ExampleContext.get() is None


def test_flow_run_context():
    @flow
    def foo():
        pass

    test_id = uuid4()
    test_client = OrionClient()

    with FlowRunContext(flow=foo, flow_run_id=test_id, client=test_client):
        ctx = FlowRunContext.get()
        assert ctx.flow is foo
        assert ctx.flow_run_id == test_id
        assert ctx.client is test_client


def test_task_run_context():
    @task
    def foo():
        pass

    test_id = uuid4()

    with TaskRunContext(task=foo, task_run_id=test_id, flow_run_id=test_id):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run_id == test_id


def test_get_run_context_fails_on_empty():
    with pytest.raises(RuntimeError, match="could not be retrieved.*not in a flow run"):
        RunContext.get()


def test_run_context_flow_run_only():
    @flow
    def foo():
        pass

    test_id = uuid4()
    test_client = OrionClient()

    flow_run_ctx = FlowRunContext(flow=foo, flow_run_id=test_id, client=test_client)
    with flow_run_ctx:
        ctx = RunContext.get()
        assert ctx.task_run is None
        assert ctx.flow_run == flow_run_ctx


def test_get_run_context_flow_run_and_task_run():
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    test_id = uuid4()
    test_client = OrionClient()

    flow_run_ctx = FlowRunContext(flow=foo, flow_run_id=test_id, client=test_client)
    task_run_ctx = TaskRunContext(task=bar, task_run_id=test_id, flow_run_id=test_id)
    with flow_run_ctx:
        with task_run_ctx:
            ctx = RunContext.get()
            assert ctx.task_run == task_run_ctx
            assert ctx.flow_run == flow_run_ctx


def test_run_context_does_not_allow_with():
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    test_id = uuid4()
    test_client = OrionClient()

    flow_run_ctx = FlowRunContext(flow=foo, flow_run_id=test_id, client=test_client)
    task_run_ctx = TaskRunContext(task=bar, task_run_id=test_id, flow_run_id=test_id)
    run_ctx = RunContext(flow_run=flow_run_ctx, task_run=task_run_ctx)

    with pytest.raises(TypeError, match="cannot be set"):
        with run_ctx:
            pass
