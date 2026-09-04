import time
from unittest.mock import MagicMock, patch

import distributed
import pytest
from prefect_dask import DaskTaskRunner
from prefect_dask.client import PrefectDaskClient

from prefect import flow, task


def _count_prefect_tasks_in_scheduler_process(dask_scheduler) -> int:
    import gc

    gc.collect()
    return sum(
        1
        for obj in gc.get_objects()
        if type(obj).__module__ == "prefect.tasks" and type(obj).__name__ == "Task"
    )


def test_scheduler_does_not_retain_prefect_tasks():
    with distributed.LocalCluster(dashboard_address=None) as cluster:
        task_runner = DaskTaskRunner(address=cluster.scheduler_address)

        @task
        def make_range(n: int) -> list[int]:
            return list(range(n))

        @task
        def identity(x: int) -> int:
            return x

        @flow(task_runner=task_runner)
        def test_flow(n: int):
            values = make_range.submit(n)
            futures = identity.map(values)
            return [future.result() for future in futures]

        assert test_flow(10) == list(range(10))

        with distributed.Client(cluster) as client:
            for _ in range(20):
                retained_prefect_tasks = client.run_on_scheduler(
                    _count_prefect_tasks_in_scheduler_process
                )
                if retained_prefect_tasks == 0:
                    break
                time.sleep(0.05)

        assert retained_prefect_tasks == 0


def test_zero_worker_adaptive_cluster_can_run_prefect_task():
    with distributed.LocalCluster(n_workers=0, dashboard_address=None) as cluster:
        cluster.adapt(minimum=0, maximum=1)
        task_runner = DaskTaskRunner(address=cluster.scheduler_address)

        @task
        def increment(value: int) -> int:
            return value + 1

        @flow(task_runner=task_runner)
        def test_flow() -> int:
            return increment.submit(1).result()

        assert test_flow() == 2


def test_payload_futures_are_released_when_run_submission_fails():
    client = PrefectDaskClient.__new__(PrefectDaskClient)
    task_future = MagicMock()
    context_future = MagicMock()

    @task
    def noop() -> None:
        return None

    with (
        patch.object(
            PrefectDaskClient,
            "_submit_payload",
            side_effect=[task_future, context_future],
        ),
        patch.object(
            PrefectDaskClient,
            "_submit_prefect_run",
            side_effect=RuntimeError("submission failed"),
        ),
        pytest.raises(RuntimeError, match="submission failed"),
    ):
        client.submit(noop, parameters={}, wait_for=[])

    task_future.release.assert_called_once_with()
    context_future.release.assert_called_once_with()
