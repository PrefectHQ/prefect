import distributed
from prefect_dask import DaskTaskRunner

from prefect import flow, task


def _count_retained_prefect_tasks_in_dask_specs(dask_scheduler) -> int:
    import gc

    def is_prefect_task(obj) -> bool:
        obj_type = type(obj)
        return obj_type.__module__ == "prefect.tasks" and obj_type.__name__ == "Task"

    def contains_prefect_task(obj) -> bool:
        seen: set[int] = set()
        stack = [obj]

        while stack:
            current = stack.pop()
            current_id = id(current)
            if current_id in seen:
                continue
            seen.add(current_id)

            if is_prefect_task(current):
                return True
            elif isinstance(current, dict):
                stack.extend(current.keys())
                stack.extend(current.values())
            elif isinstance(current, (list, tuple, set, frozenset)):
                stack.extend(current)

        return False

    return sum(
        1
        for obj in gc.get_objects()
        if type(obj).__module__ == "dask._task_spec"
        and type(obj).__name__ == "Task"
        and contains_prefect_task(
            (getattr(obj, "args", ()), getattr(obj, "kwargs", {}))
        )
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
            retained_prefect_tasks = client.run_on_scheduler(
                _count_retained_prefect_tasks_in_dask_specs
            )

        assert retained_prefect_tasks == 0
