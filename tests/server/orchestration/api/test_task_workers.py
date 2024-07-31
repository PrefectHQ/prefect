import pytest

from prefect.server.models.task_workers import observe_worker


@pytest.mark.parametrize(
    "initial_workers,certain_tasks,expected_count",
    [
        ({"worker1": ["task1"]}, None, 1),
        ({"worker1": ["task1"], "worker2": ["task2"]}, ["task1"], 1),
        ({"worker1": ["task1"], "worker2": ["task2"]}, None, 2),
        ({"worker1": ["task1", "task2"], "worker2": ["task2", "task3"]}, ["task2"], 2),
    ],
    ids=[
        "one_worker_no_filter",
        "one_worker_filter",
        "two_workers_no_filter",
        "two_workers_filter",
    ],
)
async def test_read_task_workers(
    test_client, initial_workers, certain_tasks, expected_count
):
    for worker, tasks in initial_workers.items():
        await observe_worker(tasks, worker)

    response = test_client.post(
        "api/task_workers/filter",
        json={"task_worker_filter": {"task_keys": certain_tasks}}
        if certain_tasks
        else None,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == expected_count

    if expected_count > 0:
        for worker in data:
            assert worker["identifier"] in initial_workers
            assert set(worker["task_keys"]).issubset(
                set(initial_workers[worker["identifier"]])
            )
