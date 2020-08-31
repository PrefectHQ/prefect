import logging
import os
import random
import sys
import threading
import time
import uuid

import cloudpickle
import dask
import distributed
import pytest

import prefect
from prefect.engine.executors import (
    DaskExecutor,
    Executor,
    LocalDaskExecutor,
    LocalExecutor,
)


class TestBaseExecutor:
    def test_submit_raises_notimplemented(self):
        with pytest.raises(NotImplementedError):
            Executor().submit(lambda: 1)

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


class TestLocalDaskExecutor:
    def test_scheduler_defaults_to_threads(self):
        e = LocalDaskExecutor()
        assert e.scheduler == "threads"

    def test_configurable_scheduler(self):
        e = LocalDaskExecutor(scheduler="synchronous")
        assert e.scheduler == "synchronous"

        def check_scheduler(val):
            assert dask.config.get("scheduler") == val

        with dask.config.set(scheduler="threads"):
            check_scheduler("threads")
            with e.start():
                e.submit(check_scheduler, "synchronous")

    def test_normalize_scheduler(self):
        normalize = LocalDaskExecutor._normalize_scheduler
        assert normalize("THREADS") == "threads"
        for name in ["threading", "threads"]:
            assert normalize(name) == "threads"
        for name in ["multiprocessing", "processes"]:
            assert normalize(name) == "processes"
        for name in ["sync", "synchronous", "single-threaded"]:
            assert normalize(name) == "synchronous"
        with pytest.raises(ValueError):
            normalize("unknown")

    def test_submit(self):
        e = LocalDaskExecutor()
        with e.start():
            assert e.submit(lambda: 1).compute(scheduler="sync") == 1
            assert e.submit(lambda x: x, 1).compute(scheduler="sync") == 1
            assert e.submit(lambda x: x, x=1).compute(scheduler="sync") == 1
            assert e.submit(lambda: prefect).compute(scheduler="sync") is prefect

    def test_wait(self):
        e = LocalDaskExecutor()
        with e.start():
            assert e.wait(1) == 1
            assert e.wait(prefect) is prefect
            assert e.wait(e.submit(lambda: 1)) == 1
            assert e.wait(e.submit(lambda x: x, 1)) == 1
            assert e.wait(e.submit(lambda x: x, x=1)) == 1
            assert e.wait(e.submit(lambda: prefect)) is prefect

    def test_submit_sets_task_name(self):
        e = LocalDaskExecutor()
        with e.start():
            f = e.submit(lambda x: x + 1, 1, extra_context={"task_name": "inc"})
            (res,) = e.wait([f])
            assert f.key.startswith("inc-")
            assert res == 2

            f = e.submit(
                lambda x: x + 1, 1, extra_context={"task_name": "inc", "task_index": 1}
            )
            (res,) = e.wait([f])
            assert f.key.startswith("inc-1-")
            assert res == 2

    @pytest.mark.parametrize("scheduler", ["threads", "processes", "synchronous"])
    def test_only_compute_once(self, scheduler, tmpdir):
        e = LocalDaskExecutor(scheduler)

        def inc(x, path):
            if os.path.exists(path):
                raise ValueError("Should only run once!")
            with open(path, "wb"):
                pass
            return x + 1

        with e.start():
            f1 = e.submit(inc, 0, str(tmpdir.join("f1")))
            f2 = e.submit(inc, f1, str(tmpdir.join("f2")))
            f3 = e.submit(inc, f2, str(tmpdir.join("f3")))
            assert e.wait([f1]) == [1]
            assert e.wait([f2]) == [2]
            assert e.wait([f3]) == [3]
            assert e.wait([f1, f2, f3]) == [1, 2, 3]

    def test_is_pickleable(self):
        e = LocalDaskExecutor()
        post = cloudpickle.loads(cloudpickle.dumps(e))
        assert isinstance(post, LocalDaskExecutor)

    def test_is_pickleable_after_start(self):
        e = LocalDaskExecutor()
        with e.start():
            post = cloudpickle.loads(cloudpickle.dumps(e))
            assert isinstance(post, LocalDaskExecutor)
            assert post._pool is None

    @pytest.mark.parametrize("scheduler", ["threads", "processes", "synchronous"])
    @pytest.mark.parametrize("num_workers", [None, 2])
    def test_temporary_pool_created_of_proper_size_and_kind(
        self, scheduler, num_workers
    ):
        from dask.system import CPU_COUNT
        from multiprocessing.pool import Pool, ThreadPool

        e = LocalDaskExecutor(scheduler, num_workers=num_workers)
        with e.start():
            if scheduler == "synchronous":
                assert e._pool is None
            else:
                sol = num_workers or CPU_COUNT
                kind = ThreadPool if scheduler == "threads" else Pool
                assert isinstance(e._pool, kind)
                assert e._pool._processes == sol
        assert e._pool is None

    @pytest.mark.parametrize("scheduler", ["threads", "processes", "synchronous"])
    def test_interrupt_stops_running_tasks_quickly(self, scheduler):
        # Windows implements `queue.get` using polling,
        # which means we can set an exception to interrupt the call to `get`.
        # Python 3 on other platforms requires sending SIGINT to the main thread.
        if os.name == "nt":
            from _thread import interrupt_main
        else:
            main_thread = threading.get_ident()

            def interrupt_main():
                import signal

                signal.pthread_kill(main_thread, signal.SIGINT)

        def long_task():
            for i in range(50):
                time.sleep(0.1)

        e = LocalDaskExecutor(scheduler)
        try:
            interrupter = threading.Timer(0.5, interrupt_main)
            interrupter.start()
            start = time.time()
            with e.start():
                e.wait(e.submit(long_task))
        except KeyboardInterrupt:
            pass
        except Exception:
            assert False, "Failed to interrupt"
        stop = time.time()
        if stop - start > 4:
            assert False, "Failed to interrupt"


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


@pytest.mark.parametrize("executor", ["mproc", "mthread", "sync"], indirect=True)
def test_submit_does_not_assume_pure_functions(executor):
    def random_fun():
        return random.random()

    with executor.start():
        one = executor.wait(executor.submit(random_fun))
        two = executor.wait(executor.submit(random_fun))

    assert one != two


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
            time.sleep(random.random() * 0.25 + 0.5)
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
            assert executor.client_kwargs == {"set_as_default": False}

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

    def test_local_cluster_adapt(self):
        adapt_kwargs = {"minimum": 1, "maximum": 1}
        called_with = None

        class MyCluster(distributed.LocalCluster):
            def adapt(self, **kwargs):
                nonlocal called_with
                called_with = kwargs
                super().adapt(**kwargs)

        executor = DaskExecutor(
            cluster_class=MyCluster,
            cluster_kwargs={"processes": False, "n_workers": 0},
            adapt_kwargs=adapt_kwargs,
        )

        assert executor.adapt_kwargs == adapt_kwargs

        with executor.start():
            res = executor.wait(executor.submit(lambda x: x + 1, 1))
            assert res == 2

        assert called_with == adapt_kwargs

    def test_cluster_class_and_kwargs(self):
        pytest.importorskip("distributed.deploy.spec")
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
        assert executor.client_kwargs == {"set_as_default": False}

    def test_deprecated_client_kwargs(self):
        with pytest.warns(UserWarning, match="client_kwargs"):
            executor = DaskExecutor(
                cluster_class="distributed.LocalCluster",
                set_as_default=True,
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
                address="localhost:8787",
                cluster_class=distributed.LocalCluster,
            )

    def test_prep_dask_kwargs(self):
        executor = DaskExecutor()
        kwargs = executor._prep_dask_kwargs(
            dict(task_name="FISH!", task_tags=["dask-resource:GPU=1"])
        )
        assert kwargs["key"].startswith("FISH!-")
        assert kwargs["resources"] == {"GPU": 1.0}

        kwargs = executor._prep_dask_kwargs(
            dict(task_name="FISH!", task_tags=["dask-resource:GPU=1"], task_index=1)
        )
        assert kwargs["key"].startswith("FISH!-1-")

    def test_submit_sets_task_name(self, mthread):
        with mthread.start():
            fut = mthread.submit(lambda x: x + 1, 1, extra_context={"task_name": "inc"})
            (res,) = mthread.wait([fut])
            assert fut.key.startswith("inc-")
            assert res == 2

            fut = mthread.submit(
                lambda x: x + 1, 1, extra_context={"task_name": "inc", "task_index": 1}
            )
            (res,) = mthread.wait([fut])
            assert fut.key.startswith("inc-1-")
            assert res == 2

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_is_pickleable(self, executor):
        post = cloudpickle.loads(cloudpickle.dumps(executor))
        assert isinstance(post, DaskExecutor)
        assert post.client is None

    @pytest.mark.parametrize("executor", ["mproc", "mthread"], indirect=True)
    def test_is_pickleable_after_start(self, executor):
        with executor.start():
            post = cloudpickle.loads(cloudpickle.dumps(executor))
            assert isinstance(post, DaskExecutor)
            assert post.client is None
            assert post._futures is None
            assert post._should_run_var is None

    def test_executor_logs_worker_events(self, caplog):
        caplog.set_level(logging.DEBUG, logger="prefect")
        with distributed.Client(
            n_workers=1, processes=False, set_as_default=False
        ) as client:
            executor = DaskExecutor(address=client.scheduler.address)
            with executor.start():
                client.cluster.scale(4)
                while len(client.scheduler_info()["workers"]) < 4:
                    time.sleep(0.1)
                client.cluster.scale(1)
                while len(client.scheduler_info()["workers"]) > 1:
                    time.sleep(0.1)

        assert any("Worker %s added" == rec.msg for rec in caplog.records)
        assert any("Worker %s removed" == rec.msg for rec in caplog.records)

    @pytest.mark.parametrize("kind", ["external", "inproc"])
    def test_exit_early_with_external_or_inproc_cluster_waits_for_pending_futures(
        self, kind, monkeypatch
    ):
        key = "TESTING_%s" % uuid.uuid4().hex

        monkeypatch.setenv(key, "initial")

        def slow():
            time.sleep(0.5)
            os.environ[key] = "changed"

        def pending(x):
            # This function shouldn't ever start, since it's pending when the
            # shutdown signal is received
            os.environ[key] = "changed more"

        if kind == "external":
            with distributed.Client(processes=False, set_as_default=False) as client:
                executor = DaskExecutor(address=client.scheduler.address)
                with executor.start():
                    fut = executor.submit(slow)
                    fut2 = executor.submit(pending, fut)  # noqa
                    time.sleep(0.2)
                assert os.environ[key] == "changed"

        elif kind == "inproc":
            executor = DaskExecutor(cluster_kwargs={"processes": False})
            with executor.start():
                fut = executor.submit(slow)
                fut2 = executor.submit(pending, fut)  # noqa
                time.sleep(0.2)
            assert os.environ[key] == "changed"

        assert executor.client is None
        assert executor._futures is None
        assert executor._should_run_var is None

    def test_temporary_cluster_forcefully_cancels_pending_tasks(self, tmpdir):
        filname = tmpdir.join("signal")

        def slow():
            time.sleep(10)
            with open(filname, "w") as f:
                f.write("Got here")

        executor = DaskExecutor()
        with executor.start():
            start = time.time()
            fut = executor.submit(slow)  # noqa
            time.sleep(0.1)
        stop = time.time()
        # Cluster shutdown before task could complete
        assert stop - start < 5
        assert not os.path.exists(filname)
