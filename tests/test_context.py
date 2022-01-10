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
from prefect.task_runners import SequentialTaskRunner


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


async def test_flow_run_context(orion_client):
    @flow
    def foo():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await orion_client.create_flow_run(foo)

    with FlowRunContext(
        flow=foo, flow_run=flow_run, client=orion_client, task_runner=test_task_runner
    ):
        ctx = FlowRunContext.get()
        assert ctx.flow is foo
        assert ctx.flow_run == flow_run
        assert ctx.client is orion_client
        assert ctx.task_runner is test_task_runner
        assert isinstance(ctx.start_time, DateTime)


async def test_task_run_context(orion_client, flow_run):
    @task
    def foo():
        pass

    task_run = await orion_client.create_task_run(foo, flow_run.id, dynamic_key="")

    with TaskRunContext(task=foo, task_run=task_run, client=orion_client):
        ctx = TaskRunContext.get()
        assert ctx.task is foo
        assert ctx.task_run == task_run
        assert isinstance(ctx.start_time, DateTime)


async def test_get_run_context(orion_client):
    @flow
    def foo():
        pass

    @task
    def bar():
        pass

    test_task_runner = SequentialTaskRunner()
    flow_run = await orion_client.create_flow_run(foo)
    task_run = await orion_client.create_task_run(bar, flow_run.id, dynamic_key="")

    with pytest.raises(RuntimeError):
        get_run_context()

    with FlowRunContext(
        flow=foo, flow_run=flow_run, client=orion_client, task_runner=test_task_runner
    ) as flow_ctx:
        assert get_run_context() is flow_ctx

        with TaskRunContext(
            task=bar, task_run=task_run, client=orion_client
        ) as task_ctx:
            assert get_run_context() is task_ctx, "Task context takes precendence"

        assert get_run_context() is flow_ctx, "Flow context is restored and retrieved"
