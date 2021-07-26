import pytest

from prefect import flow
from prefect.tasks import task
from prefect.futures import PrefectFuture


class TestTaskCall:
    def test_task_called_outside_flow_raises(self):
        @task
        def foo():
            pass

        with pytest.raises(
            RuntimeError, match="Tasks cannot be called outside of a flow"
        ):
            foo()

    def test_task_called_inside_flow(self):
        @task
        def foo(x):
            return x

        @flow
        def bar():
            future = foo(1)
            assert isinstance(future, PrefectFuture)
            assert future.result() == 1

        bar()
