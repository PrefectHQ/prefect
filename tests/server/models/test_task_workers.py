import pytest

from prefect.server.models.task_workers import InMemoryTaskWorkerTracker


@pytest.fixture
async def tracker():
    return InMemoryTaskWorkerTracker()


@pytest.mark.parametrize(
    "task_keys,task_worker_id",
    [(["task1", "task2"], "worker1"), (["task3"], "worker2"), ([], "worker3")],
    ids=["task_keys", "no_task_keys", "empty_task_keys"],
)
async def test_observe_and_get_worker(tracker, task_keys, task_worker_id):
    await tracker.observe_worker(task_keys, task_worker_id)
    workers = await tracker.get_all_workers()
    assert len(workers) == 1
    assert workers[0].identifier == task_worker_id
    assert set(workers[0].task_keys) == set(task_keys)


@pytest.mark.parametrize(
    "initial_tasks,forget_id,expected_count",
    [
        ({"worker1": ["task1"], "worker2": ["task2"]}, "worker1", 1),
        ({"worker1": ["task1"]}, "worker1", 0),
        ({"worker1": ["task1"]}, "worker2", 1),
    ],
    ids=["forget_worker", "forget_no_worker", "forget_empty_worker"],
)
async def test_forget_worker(tracker, initial_tasks, forget_id, expected_count):
    for worker, tasks in initial_tasks.items():
        await tracker.observe_worker(tasks, worker)
    await tracker.forget_worker(forget_id)
    workers = await tracker.get_all_workers()
    assert len(workers) == expected_count


@pytest.mark.parametrize(
    "observed_workers,query_tasks,expected_workers",
    [
        (
            {"worker1": ["task1", "task2"], "worker2": ["task2", "task3"]},
            ["task2"],
            {"worker1", "worker2"},
        ),
        ({"worker1": ["task1"], "worker2": ["task2"]}, ["task3"], set()),
        ({"worker1": ["task1"], "worker2": ["task2"]}, [], {"worker1", "worker2"}),
    ],
    ids=["filter_tasks", "filter_tasks_and_task_keys", "no_filter"],
)
async def test_get_workers_for_task_keys(
    tracker, observed_workers, query_tasks, expected_workers
):
    for worker, tasks in observed_workers.items():
        await tracker.observe_worker(tasks, worker)
    workers = await tracker.get_workers_for_task_keys(query_tasks)
    assert {w.identifier for w in workers} == expected_workers
