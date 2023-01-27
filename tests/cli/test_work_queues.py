import pytest

import prefect.exceptions
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import sync_compatible


@sync_compatible
async def read_queue(orion_client, name):
    return await orion_client.read_work_queue_by_name(name)


def test_create_work_queue():
    invoke_and_assert(
        command="work-queue create q-name",
        expected_output_contains=[
            "Created work queue with properties:",
            "name - 'q-name'",
        ],
        expected_code=0,
    )


def test_create_work_queue_with_limit():
    invoke_and_assert(
        command="work-queue create q-name -l 3",
        expected_output_contains=[
            "Created work queue with properties:",
            "concurrency limit - 3",
        ],
        expected_code=0,
    )


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_create_work_queue_with_tags():
    invoke_and_assert(
        command="work-queue create q-name -t blue -t red",
        expected_output_contains=[
            "Supplying `tags` for work queues is deprecated",
            "tags - blue, red",
        ],
        expected_code=0,
    )


def test_set_concurrency_limit(orion_client, work_queue):
    assert work_queue.concurrency_limit is None
    invoke_and_assert(
        command=f"work-queue set-concurrency-limit {work_queue.name} 5",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert q.concurrency_limit == 5


def test_set_concurrency_limit_by_id(orion_client, work_queue):
    assert work_queue.concurrency_limit is None
    invoke_and_assert(
        command=f"work-queue set-concurrency-limit {work_queue.id} 5",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert q.concurrency_limit == 5


def test_clear_concurrency_limit(orion_client, work_queue):
    invoke_and_assert(command=f"work-queue set-concurrency-limit {work_queue.name} 5")
    invoke_and_assert(
        command=f"work-queue clear-concurrency-limit {work_queue.name}",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert q.concurrency_limit is None


def test_clear_concurrency_limit_by_id(orion_client, work_queue):
    invoke_and_assert(command=f"work-queue set-concurrency-limit {work_queue.name} 5")
    invoke_and_assert(
        command=f"work-queue clear-concurrency-limit {work_queue.id}",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert q.concurrency_limit is None


def test_pause(orion_client, work_queue):
    assert not work_queue.is_paused
    invoke_and_assert(
        command=f"work-queue pause {work_queue.name}",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert q.is_paused


def test_pause_by_id(orion_client, work_queue):
    assert not work_queue.is_paused
    invoke_and_assert(
        command=f"work-queue pause {work_queue.id}",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert q.is_paused


def test_resume(orion_client, work_queue):
    invoke_and_assert(command=f"work-queue pause {work_queue.name}")
    invoke_and_assert(
        command=f"work-queue resume {work_queue.name}",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert not q.is_paused


def test_resume_by_id(orion_client, work_queue):
    invoke_and_assert(command=f"work-queue pause {work_queue.name}")
    invoke_and_assert(
        command=f"work-queue resume {work_queue.id}",
        expected_code=0,
    )
    q = read_queue(orion_client, work_queue.name)
    assert not q.is_paused


def test_inspect(work_queue):
    invoke_and_assert(
        command=f"work-queue inspect {work_queue.name}",
        expected_output_contains=[f"id='{work_queue.id}'", f"name={work_queue.name!r}"],
        expected_code=0,
    )


def test_inspect_by_id(work_queue):
    invoke_and_assert(
        command=f"work-queue inspect {work_queue.id}",
        expected_output_contains=[f"id='{work_queue.id}'", f"name={work_queue.name!r}"],
        expected_code=0,
    )


def test_delete(orion_client, work_queue):
    invoke_and_assert(
        command=f"work-queue delete {work_queue.name}",
        expected_code=0,
    )
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        read_queue(orion_client, work_queue.name)


def test_delete_by_id(orion_client, work_queue):
    invoke_and_assert(
        command=f"work-queue delete {work_queue.id}",
        expected_code=0,
    )
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        read_queue(orion_client, work_queue.name)
