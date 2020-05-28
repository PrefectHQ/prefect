import logging
import random
import sys
import time
from unittest.mock import MagicMock

import cloudpickle
import distributed
import pytest

import prefect
from prefect.engine.executors import (
    DaskExecutor,
    Executor,
    LocalDaskExecutor,
    LocalExecutor,
    SynchronousExecutor,
)


class TestBaseExecutor:
    def test_submit_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().submit(lambda: 1)

    def test_map_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().map(lambda: 1)

    def test_wait_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().wait([1])

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
    def test_sync_is_depcrecated(self):
        with pytest.warns(UserWarning) as w:
            e = SynchronousExecutor()

        assert "deprecated" in str(w[0].message)
        assert "LocalDaskExecutor" in str(w[0].message)
        assert isinstance(e, LocalDaskExecutor)
        assert e.scheduler == "synchronous"


class TestLocalDaskExecutor:
    def test_scheduler_defaults_to_threads(self):
        e = LocalDaskExecutor()
        assert e.scheduler == "threads"

    def test_responds_to_kwargs(self):
        e = LocalDaskExecutor(scheduler="threads")
        assert e.scheduler == "threads"

    def test_start_yields_cfg(self):
        with LocalDaskExecutor(scheduler="threads").start() as cfg:
            assert cfg["scheduler"] == "threads"

    def test_submit(self):
        e = LocalDaskExecutor()
        with e.start():
            assert e.submit(lambda: 1).compute() == 1
            assert e.submit(lambda x: x, 1).compute() == 1
            assert e.submit(lambda x: x, x=1).compute() == 1
            assert e.submit(lambda: prefect).compute() is prefect

    def test_wait(self):
        e = LocalDaskExecutor()
        with e.start():
            assert e.wait(1) == 1
            assert e.wait(prefect) is prefect
            assert e.wait(e.submit(lambda: 1)) == 1
            assert e.wait(e.submit(lambda x: x, 1)) == 1
            assert e.wait(e.submit(lambda x: x, x=1)) == 1
            assert e.wait(e.submit(lambda: prefect)) is prefect

    def test_is_pickleable(self):
        e = LocalDaskExecutor()
        post = cloudpickle.loads(cloudpickle.dumps(e))
        assert isinstance(post, LocalDaskExecutor)

    def test_is_pickleable_after_start(self):
        e = LocalDaskExecutor()
        with e.start():
            post = cloudpickle.loads(cloudpickle.dumps(e))
            assert isinstance(post, LocalDaskExecutor)

    def test_map_iterates_over_multiple_args(self):
        def map_fn(x, y):
            return x + y

        e = LocalDaskExecutor()
        with e.start():
            res = e.wait(e.map(map_fn, [1, 2], [1, 3]))
        assert res == [2, 5]

    def test_map_doesnt_do_anything_for_empty_list_input(self):
        def map_fn(*args):
            raise ValueError("map_fn was called")

        e = LocalDaskExecutor()
        with e.start():
            res = e.wait(e.map(map_fn))
        assert res == []

    def test_map_with_synchronous_scheduler(self):
        def map_fn(x, y):
            return x + y

        e = LocalDaskExecutor(scheduler="synchronous")
        with e.start():
            res = e.wait(e.map(map_fn, [1, 2], [1, 3]))
        assert res == [2, 5]

    def test_map_with_threads_scheduler(self):
        def map_fn(x, y):
            return x + y

        e = LocalDaskExecutor(scheduler="threads")
        with e.start():
            res = e.wait(e.map(map_fn, [1, 2], [1, 3]))
        assert res == [2, 5]

    def test_map_fails_with_processes_executor(self):
        def map_fn(x, y):
            return x + y

        e = LocalDaskExecutor(scheduler="processes")
        with pytest.raises(RuntimeError):
            with e.start():
                e.wait(e.map(map_fn, [1, 2], [1, 3]))


class TestLocalExecutor:
    def test_submit(self):
        """LocalExecutor directly executes the function"""
        assert LocalExecutor().submit(lambda: 1) == 1
        assert LocalExecutor().submit(lambda x: x, 1) == 1
        assert LocalExecutor().submit(lambda x: x, x=1) == 1
        assert LocalExecutor().submit(lambda: prefect) is prefect

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

    def test_map_iterates_over_multiple_args(self):
        def map_fn(x, y):
            return x + y

        e = LocalExecutor()
        with e.start():
            res = e.wait(e.map(map_fn, [1, 2], [1, 3]))
        assert res == [2, 5]

    def test_map_doesnt_do_anything_for_empty_list_input(self):
        def map_fn(*args):
            raise ValueError("map_fn was called")

        e = LocalExecutor()
        with e.start():
            res = e.wait(e.map(map_fn))
        assert res == []


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
            executor.wait(executor.submit(executor.timeout_handler, slow_fn, timeout=1))


def test_dask_processes_executor_handles_timeouts(mproc):
    with mproc.start():
        with pytest.raises(TimeoutError, match="Execution timed out"):
            mproc.wait(mproc.submit(mproc.timeout_handler, time.sleep, 2, timeout=1))


class TestDaskExecutor:
    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_submit_and_wait(self, executor):
        to_compute = {}
        with executor.start():
            to_compute["x"] = executor.submit(lambda: 3)
            to_compute["y"] = executor.submit(lambda x: x + 1, to_compute["x"])
            x = executor.wait(to_compute["x"])
            y = executor.wait(to_compute["y"])
        assert x == 3
        assert y == 4

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Nondeterministically fails on Windows machines"
    )
    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_runs_in_parallel(self, executor):
        # related: "https://stackoverflow.com/questions/52121686/why-is-dask-distributed-not-parallelizing-the-first-run-of-my-workflow"

        def record_times():
            start_time = time.time()
            time.sleep(random.random() * 0.25 + 0.1)
            end_time = time.time()
            return start_time, end_time

        with executor.start():
            a = executor.submit(record_times)
            b = executor.submit(record_times)
            a, b = executor.wait([a, b])

        a_start, a_end = a
        b_start, b_end = b

        assert a_start < b_end
        assert b_start < a_end

    def test_connect_to_running_cluster(self):
        with distributed.Client(processes=False, set_as_default=False) as client:
            executor = DaskExecutor(address=client.scheduler.address)
            assert executor.address == client.scheduler.address
            assert executor.cluster_class is None
            assert executor.cluster_kwargs is None
            assert executor.client_kwargs == {}

            with executor.start():
                res = executor.wait(executor.submit(lambda x: x + 1, 1))
                assert res == 2

    def test_start_local_cluster(self):
        executor = DaskExecutor(cluster_kwargs={"processes": False})
        assert executor.cluster_class == distributed.LocalCluster
        assert executor.cluster_kwargs == {
            "processes": False,
            "silence_logs": logging.CRITICAL,
        }

        with executor.start():
            res = executor.wait(executor.submit(lambda x: x + 1, 1))
            assert res == 2

    def test_cluster_class_and_kwargs(self):
        executor = DaskExecutor(
            cluster_class="distributed.deploy.spec.SpecCluster",
            cluster_kwargs={"some_kwarg": "some_val"},
            client_kwargs={"set_as_default": True},
        )
        assert executor.cluster_class == distributed.deploy.spec.SpecCluster
        assert executor.cluster_kwargs == {"some_kwarg": "some_val"}
        assert executor.client_kwargs == {"set_as_default": True}

        class TestCluster(object):
            pass

        executor = DaskExecutor(cluster_class=TestCluster)
        assert executor.cluster_class == TestCluster

    def test_deprecated_local_processes(self):
        with pytest.warns(UserWarning, match="local_processes"):
            executor = DaskExecutor(
                cluster_class="distributed.LocalCluster",
                client_kwargs={"set_as_default": True},
                local_processes=True,
            )
        assert executor.cluster_class == distributed.LocalCluster
        assert executor.cluster_kwargs == {
            "processes": True,
            "silence_logs": logging.CRITICAL,
        }
        assert executor.client_kwargs == {"set_as_default": True}

        # When not using a LocalCluster, `local_processes` warns, but isn't
        # added to the kwargs
        with pytest.warns(UserWarning, match="local_processes"):

            class TestCluster(object):
                pass

            executor = DaskExecutor(cluster_class=TestCluster, local_processes=True)

        assert executor.cluster_class == TestCluster
        assert executor.cluster_kwargs == {}
        assert executor.client_kwargs == {}

    def test_deprecated_client_kwargs(self):
        with pytest.warns(UserWarning, match="client_kwargs"):
            executor = DaskExecutor(
                cluster_class="distributed.LocalCluster", set_as_default=True,
            )
        assert executor.cluster_kwargs == {"silence_logs": logging.CRITICAL}
        assert executor.client_kwargs == {"set_as_default": True}

    def test_local_address_deprecated(self):
        with pytest.warns(UserWarning, match="local"):
            executor = DaskExecutor(address="local")
        assert executor.address is None
        assert executor.cluster_class == distributed.LocalCluster
        assert executor.cluster_kwargs == {"silence_logs": logging.CRITICAL}

    @pytest.mark.parametrize("debug", [True, False])
    def test_debug_is_converted_to_silence_logs(self, debug):
        executor = DaskExecutor(debug=debug)
        level = logging.WARNING if debug else logging.CRITICAL
        assert executor.cluster_kwargs["silence_logs"] == level

    def test_cant_specify_both_address_and_cluster_class(self):
        with pytest.raises(ValueError):
            DaskExecutor(
                address="localhost:8787", cluster_class=distributed.LocalCluster,
            )

    def test_task_names_are_passed_to_submit(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(distributed, "Client", client)
        executor = DaskExecutor()
        with executor.start():
            with prefect.context(task_full_name="FISH!"):
                executor.submit(lambda: None)
        kwargs = client.return_value.__enter__.return_value.submit.call_args[1]
        assert kwargs["key"].startswith("FISH!")

    def test_task_names_are_passed_to_map(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(distributed, "Client", client)
        executor = DaskExecutor()
        with executor.start():
            with prefect.context(task_full_name="FISH![0]"):
                executor.map(lambda: None, [1, 2])
        kwargs = client.return_value.__enter__.return_value.map.call_args[1]
        assert kwargs["key"].startswith("FISH![0]")

    def test_context_tags_are_passed_to_submit(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(distributed, "Client", client)
        executor = DaskExecutor()
        with executor.start():
            with prefect.context(task_tags=["dask-resource:GPU=1"]):
                executor.submit(lambda: None)
        kwargs = client.return_value.__enter__.return_value.submit.call_args[1]
        assert kwargs["resources"] == {"GPU": 1.0}

    def test_context_tags_are_passed_to_map(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(distributed, "Client", client)
        executor = DaskExecutor()
        with executor.start():
            with prefect.context(task_tags=["dask-resource:GPU=1"]):
                executor.map(lambda: None, [1, 2])
        kwargs = client.return_value.__enter__.return_value.map.call_args[1]
        assert kwargs["resources"] == {"GPU": 1.0}

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_is_pickleable(self, executor):
        post = cloudpickle.loads(cloudpickle.dumps(executor))
        assert isinstance(post, DaskExecutor)

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_is_pickleable_after_start(self, executor):
        post = cloudpickle.loads(cloudpickle.dumps(executor))
        assert isinstance(post, DaskExecutor)

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_map_iterates_over_multiple_args(self, executor):
        def map_fn(x, y):
            return x + y

        with executor.start():
            res = executor.wait(executor.map(map_fn, [1, 2], [1, 3]))
            assert res == [2, 5]

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_map_doesnt_do_anything_for_empty_list_input(self, executor):
        def map_fn(*args):
            raise ValueError("map_fn was called")

        with executor.start():
            res = executor.wait(executor.map(map_fn))
        assert res == []
