import pytest
import time

import prefect
from prefect.engine.executors import DaskExecutor, Executor, LocalExecutor


class TestBaseExecutor:
    def test_submit_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().submit(lambda: 1)

    def test_submit_with_context_requires_context_kwarg(self):
        with pytest.raises(TypeError) as exc:
            Executor().submit_with_context(lambda: 1)
        assert "missing 1 required keyword-only argument: 'context'" in str(exc.value)

    def test_submit_with_context_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().submit_with_context(lambda: 1, context=None)

    def test_wait_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().wait([1])

    def test_queue_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().queue(2)

    def test_start_doesnt_do_anything(self):
        with Executor().start():
            assert True


class TestLocalExecutor:
    def test_submit(self):
        """LocalExecutor directly executes the function"""
        assert LocalExecutor().submit(lambda: 1) == 1
        assert LocalExecutor().submit(lambda x: x, 1) == 1
        assert LocalExecutor().submit(lambda x: x, x=1) == 1
        assert LocalExecutor().submit(lambda: prefect) is prefect

    def test_submit_with_context(self):
        context_fn = lambda: prefect.context.get("abc")
        context = dict(abc="abc")

        assert LocalExecutor().submit(context_fn) is None
        with prefect.context(context):
            assert LocalExecutor().submit(context_fn) == "abc"
        assert LocalExecutor().submit_with_context(context_fn, context=context) == "abc"

    def test_submit_with_context_requires_context_kwarg(self):
        with pytest.raises(TypeError) as exc:
            LocalExecutor().submit_with_context(lambda: 1)
        assert "missing 1 required keyword-only argument: 'context'" in str(exc.value)

    def test_wait(self):
        """LocalExecutor's wait() method just returns its input"""
        assert LocalExecutor().wait(1) == 1
        assert LocalExecutor().wait(prefect) is prefect


class TestDaskExecutor:
    def test_submit_and_wait(self):
        to_compute = {}
        to_compute["x"] = DaskExecutor().submit(lambda: 3)
        to_compute["y"] = DaskExecutor().submit(lambda x: x + 1, to_compute["x"])
        computed = DaskExecutor().wait(to_compute)
        assert "x" in computed
        assert "y" in computed
        assert computed["x"] == 3
        assert computed["y"] == 4

    def test_submit_with_context(self):
        executor = DaskExecutor()
        context_fn = lambda: prefect.context.get("abc")
        context = dict(abc="abc")

        assert executor.wait(executor.submit(context_fn)) is None
        with prefect.context(context):
            assert executor.wait(executor.submit(context_fn)) == "abc"
        fut = executor.submit_with_context(context_fn, context=context)
        context.clear()
        assert executor.wait(fut) == "abc"

    def test_submit_with_context_requires_context_kwarg(self):
        with pytest.raises(TypeError) as exc:
            DaskExecutor().submit_with_context(lambda: 1)
        assert "missing 1 required keyword-only argument: 'context'" in str(exc.value)

    @pytest.mark.parametrize("scheduler", ["threads", "processes"])
    def test_executor_implements_parallelism(self, scheduler):
        executor = DaskExecutor(scheduler=scheduler)

        @prefect.task
        def timed():
            time.sleep(0.1)
            return time.time()

        with prefect.Flow() as f:
            a, b = timed(), timed()

        res = f.run(executor=executor, return_tasks=f.tasks)
        times = [s.result for t, s in res.result.items()]
        assert abs(times[0] - times[1]) < 0.1
