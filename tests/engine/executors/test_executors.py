import pytest
import sys
import tempfile
import time

import prefect
from prefect.engine.executors import Executor, Executor, LocalExecutor

if sys.version_info >= (3, 5):
    from prefect.engine.executors import DaskExecutor


class TestBaseExecutor:
    def test_submit_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().submit(lambda: 1)

    def test_map_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().map(lambda: 1)

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


@pytest.mark.skipif(
    sys.version_info < (3, 5), reason="dask.distributed does not support Python 3.4"
)
class TestDaskExecutor:
    @pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
    def test_submit_and_wait(self, executor):
        to_compute = {}
        with executor.start():
            to_compute["x"] = executor.submit(lambda: 3)
            to_compute["y"] = executor.submit(lambda x: x + 1, to_compute["x"])
            computed = executor.wait(to_compute)
        assert "x" in computed
        assert "y" in computed
        assert computed["x"] == 3
        assert computed["y"] == 4

    @pytest.mark.parametrize("executor", ["threaded"], indirect=True)
    def test_submit_with_context(self, executor):
        context_fn = lambda: prefect.context.get("abc")
        context = dict(abc="abc")

        with executor.start():
            assert executor.wait(executor.submit(context_fn)) is None
            with prefect.context(context):
                assert executor.wait(executor.submit(context_fn)) == "abc"
            fut = executor.submit_with_context(context_fn, context=context)
            context.clear()
            assert executor.wait(fut) == "abc"

    @pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
    def test_submit_with_context_requires_context_kwarg(self, executor):
        with pytest.raises(TypeError) as exc:
            with executor.start():
                executor.submit_with_context(lambda: 1)
        assert "missing 1 required keyword-only argument: 'context'" in str(exc.value)

    @pytest.mark.parametrize("executor", ["multi", "threaded"], indirect=True)
    def test_runs_in_parallel(self, executor):
        if executor.processes:
            pytest.skip(
                "https://stackoverflow.com/questions/52121686/why-is-dask-distributed-not-parallelizing-the-first-run-of-my-workflow"
            )
        num = 50

        def alice(fname):
            for _ in range(num):
                with open(fname, "a") as f:
                    f.write("alice was here\n")

        def bob(fname):
            for _ in range(num):
                with open(fname, "a") as f:
                    f.write("bob was here\n")

        with tempfile.NamedTemporaryFile() as f:
            with executor.start() as client:
                a = client.submit(alice, f.name)
                b = client.submit(bob, f.name)
                client.gather([a, b])

            with open(f.name, "r") as ff:
                output = ff.readlines()

        alice_first = ["alice was here\n"] * num + ["bob was here\n"] * num
        bob_first = ["bob was here\n"] * num + ["alice was here\n"] * num
        assert output != alice_first
        assert output != bob_first
