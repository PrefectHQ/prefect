import cloudpickle
import datetime
import logging
import pytest
import random
import sys
import tempfile
import time

from unittest.mock import MagicMock

import prefect
from prefect.engine.executors import Executor, LocalExecutor, SynchronousExecutor

if sys.version_info >= (3, 5):
    from prefect.engine.executors import DaskExecutor


class TestBaseExecutor:
    def test_submit_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().submit(lambda: 1)

    def test_map_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().map(lambda: 1, upstream_states={})

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

    def test_is_pickleable(self):
        e = Executor()
        post = cloudpickle.loads(cloudpickle.dumps(e))
        assert isinstance(post, Executor)

    def test_is_pickleable_after_start(self):
        e = Executor()
        with e.start():
            post = cloudpickle.loads(cloudpickle.dumps(e))
            assert isinstance(post, Executor)


class TestSyncExecutor:
    def test_submit(self):
        assert SynchronousExecutor().submit(lambda: 1).compute() == 1
        assert SynchronousExecutor().submit(lambda x: x, 1).compute() == 1
        assert SynchronousExecutor().submit(lambda x: x, x=1).compute() == 1
        assert SynchronousExecutor().submit(lambda: prefect).compute() is prefect

    def test_submit_with_context(self):
        context_fn = lambda: prefect.context.get("abc")
        context = dict(abc="abc")

        assert SynchronousExecutor().submit(context_fn).compute() is None
        with prefect.context(context):
            assert SynchronousExecutor().submit(context_fn).compute() is None
        assert (
            SynchronousExecutor()
            .submit_with_context(context_fn, context=context)
            .compute()
            == "abc"
        )

    def test_submit_with_context_requires_context_kwarg(self):
        with pytest.raises(TypeError) as exc:
            SynchronousExecutor().submit_with_context(lambda: 1)
        assert "missing 1 required keyword-only argument: 'context'" in str(exc.value)

    def test_wait(self):
        e = SynchronousExecutor()
        assert e.wait(1) == 1
        assert e.wait(prefect) is prefect
        assert e.wait(e.submit(lambda: 1)) == 1
        assert e.wait(e.submit(lambda x: x, 1)) == 1
        assert e.wait(e.submit(lambda x: x, x=1)) == 1
        assert e.wait(e.submit(lambda: prefect)) is prefect

    def test_is_pickleable(self):
        e = SynchronousExecutor()
        post = cloudpickle.loads(cloudpickle.dumps(e))
        assert isinstance(post, SynchronousExecutor)

    def test_is_pickleable_after_start(self):
        e = SynchronousExecutor()
        with e.start():
            post = cloudpickle.loads(cloudpickle.dumps(e))
            assert isinstance(post, SynchronousExecutor)


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

    def test_is_pickleable(self):
        e = LocalExecutor()
        post = cloudpickle.loads(cloudpickle.dumps(e))
        assert isinstance(post, LocalExecutor)

    def test_is_pickleable_after_start(self):
        e = LocalExecutor()
        with e.start():
            post = cloudpickle.loads(cloudpickle.dumps(e))
            assert isinstance(post, LocalExecutor)


@pytest.mark.skipif(sys.version_info >= (3, 5), reason="Only raised in Python 3.4")
def test_importing_dask_raises_informative_import_error():
    with pytest.raises(ImportError) as exc:
        from prefect.engine.executors.dask import DaskExecutor
    assert (
        exc.value.msg == "The DaskExecutor is only locally compatible with Python 3.5+"
    )


@pytest.mark.parametrize("executor", ["mproc", "mthread", "sync"], indirect=True)
def test_submit_does_not_assume_pure_functions(executor):
    def random_fun():
        return random.random()

    with executor.start():
        one = executor.wait(executor.submit(random_fun))
        two = executor.wait(executor.submit(random_fun))

    assert one != two


@pytest.mark.parametrize("executor", ["local", "mthread", "sync"], indirect=True)
def test_executor_has_compatible_timeout_handler(executor):
    slow_fn = lambda: time.sleep(3)
    with executor.start():
        with pytest.raises(TimeoutError):
            res = executor.wait(
                executor.submit(
                    executor.timeout_handler,
                    slow_fn,
                    timeout=datetime.timedelta(seconds=1),
                )
            )


@pytest.mark.skipif(
    sys.version_info < (3, 5), reason="dask.distributed does not support Python 3.4"
)
def test_dask_processes_executor_raises_if_timeout_attempted(mproc):
    slow_fn = lambda: time.sleep(3)
    with mproc.start():
        with pytest.raises(AssertionError) as exc:
            res = mproc.wait(
                mproc.submit(
                    mproc.timeout_handler,
                    slow_fn,
                    timeout=datetime.timedelta(seconds=1),
                )
            )
    assert "daemonic" in str(exc)


@pytest.mark.skipif(
    sys.version_info < (3, 5), reason="dask.distributed does not support Python 3.4"
)
class TestDaskExecutor:
    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
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

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_submit_with_context(self, executor):
        context_fn = lambda: prefect.context.get("abc")
        context = dict(abc="abc")

        with executor.start():
            assert executor.wait(executor.submit(context_fn)) is None
            with prefect.context(context):
                assert (
                    executor.wait(executor.submit(context_fn)) is None
                )  # not inherited to subprocesses / threads
            fut = executor.submit_with_context(context_fn, context=context)
            context.clear()
            assert executor.wait(fut) == "abc"

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_submit_with_context_requires_context_kwarg(self, executor):
        with pytest.raises(TypeError) as exc:
            with executor.start():
                executor.submit_with_context(lambda: 1)
        assert "missing 1 required keyword-only argument: 'context'" in str(exc.value)

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_runs_in_parallel(self, executor):
        """This test is designed to have two tasks record and return their multiple execution times;
        if the tasks run in parallel, we expect the times to be scrambled."""
        # related: "https://stackoverflow.com/questions/52121686/why-is-dask-distributed-not-parallelizing-the-first-run-of-my-workflow"

        def record_times():
            res = []
            pause = random.randint(0, 50)
            for i in range(50):
                if i == pause:
                    time.sleep(0.1)  # add a little noise
                res.append(time.time())
            return res

        with executor.start() as client:
            a = client.submit(record_times)
            b = client.submit(record_times)
            res = client.gather([a, b])

        times = [("alice", t) for t in res[0]] + [("bob", t) for t in res[1]]
        names = [name for name, time in sorted(times, key=lambda x: x[1])]

        alice_first = ["alice"] * 50 + ["bob"] * 50
        bob_first = ["bob"] * 50 + ["alice"] * 50

        assert names != alice_first
        assert names != bob_first

    def test_init_kwargs_are_passed_to_init(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(prefect.engine.executors.dask, "Client", client)
        executor = DaskExecutor(test_kwarg="test_value")
        with executor.start():
            pass
        assert client.called
        assert client.call_args[-1]["test_kwarg"] == "test_value"

    def test_debug_is_converted_to_silence_logs(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(prefect.engine.executors.dask, "Client", client)

        # debug False
        executor = DaskExecutor(debug=False)
        with executor.start():
            pass
        assert client.called
        assert client.call_args[-1]["silence_logs"] == logging.CRITICAL

        # debug True
        executor = DaskExecutor(debug=True)
        with executor.start():
            pass
        assert client.called
        assert client.call_args[-1]["silence_logs"] == logging.WARNING

    @pytest.mark.parametrize("processes", [True, False])
    def test_is_pickleable(self, processes):
        e = DaskExecutor(processes=processes)
        post = cloudpickle.loads(cloudpickle.dumps(e))
        assert isinstance(post, DaskExecutor)

    @pytest.mark.parametrize("processes", [True, False])
    def test_is_pickleable_after_start(self, processes):
        e = DaskExecutor(processes=processes)
        with e.start():
            post = cloudpickle.loads(cloudpickle.dumps(e))
            assert isinstance(post, DaskExecutor)
