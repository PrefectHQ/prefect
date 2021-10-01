from contextvars import ContextVar
from uuid import uuid4

import pytest
from pendulum.datetime import DateTime

from prefect import flow, task
from prefect.client import OrionClient
from prefect.context import (
    ContextModel,
    FlowRunContext,
    TaskRunContext,
    get_run_context,
)
from prefect.executors import SequentialExecutor


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
    test_executor = SequentialExecutor()

    with FlowRunContext(
        flow=foo, flow_run_id=test_id, client=test_client, executor=test_executor
    ):
        ctx = FlowRunContext.get()
        assert ctx.flow is foo
        assert ctx.flow_run_id == test_id
        assert ctx.client is test_client
        assert ctx.executor is test_executor
        assert isinstance(ctx.start_time, DateTime)


def test_task_run_context():
    @task
    def foo():
        pass

    test_id = uuid4()
    test_client = OrionClient()

    with TaskRunContext(
        task=foo, task_run_id=test_id, flow_run_id=test_id, client=test_client
    ):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run_id == test_id
        assert isinstance(ctx.start_time, DateTime)


def test_get_run_context():
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    test_id = uuid4()
    test_client = OrionClient()
    test_executor = SequentialExecutor()

    with pytest.raises(RuntimeError):
        get_run_context()

    with FlowRunContext(
        flow=foo, flow_run_id=test_id, client=test_client, executor=test_executor
    ) as flow_ctx:
        assert get_run_context() is flow_ctx

        with TaskRunContext(
            task=bar, task_run_id=test_id, flow_run_id=test_id, client=test_client
        ) as task_ctx:
            assert get_run_context() is task_ctx, "Task context takes precendence"

        assert get_run_context() is flow_ctx, "Flow context is restored and retrieved"
