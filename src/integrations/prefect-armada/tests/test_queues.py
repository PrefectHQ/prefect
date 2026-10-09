from armada_client.armada import submit_pb2
from armada_client.permissions import Permissions, Subject
from prefect_armada.queues import (
    create_queue,
    create_queues,
    delete_queue,
    get_queue,
    get_queues,
    update_queue,
    update_queues,
)


async def test_create_queue(armada_credentials, mock_armada_client):
    await create_queue.fn(
        armada_credentials=armada_credentials,
        name="test-queue",
        priority_factor=2,
        user_owners=["alice"],
        group_owners=["data"],
        resource_limits={"cpu": 0.5},
    )

    queue = mock_armada_client.create_queue.call_args[0][0]
    assert queue.name == "test-queue"
    assert queue.priority_factor == 2
    assert list(queue.user_owners) == ["alice"]
    assert list(queue.group_owners) == ["data"]
    assert queue.resource_limits == {"cpu": 0.5}


async def test_create_queue_defaults_priority_factor(
    armada_credentials, mock_armada_client
):
    await create_queue.fn(armada_credentials=armada_credentials, name="test-queue")

    assert mock_armada_client.create_queue.call_args[0][0].priority_factor == 1.0


async def test_create_queue_with_permissions(armada_credentials, mock_armada_client):
    permissions = Permissions(
        subjects=[Subject(kind="Group", name="data")], verbs=["submit"]
    )

    await create_queue.fn(
        armada_credentials=armada_credentials,
        name="test-queue",
        permissions=[permissions],
    )

    queue = mock_armada_client.create_queue.call_args[0][0]
    assert queue.permissions[0].subjects[0].name == "data"
    assert list(queue.permissions[0].verbs) == ["submit"]


async def test_update_queue(armada_credentials, mock_armada_client):
    await update_queue.fn(
        armada_credentials=armada_credentials, name="test-queue", priority_factor=3
    )

    assert mock_armada_client.update_queue.call_args[0][0].priority_factor == 3


async def test_create_queues(armada_credentials, mock_armada_client):
    await create_queues.fn(
        armada_credentials=armada_credentials,
        queues=[{"name": "a", "priorityFactor": 1}, submit_pb2.Queue(name="b")],
    )

    queues = mock_armada_client.create_queues.call_args[0][0]
    assert [queue.name for queue in queues] == ["a", "b"]


async def test_update_queues(armada_credentials, mock_armada_client):
    await update_queues.fn(
        armada_credentials=armada_credentials,
        queues=[{"name": "a", "priorityFactor": 5}],
    )

    queues = mock_armada_client.update_queues.call_args[0][0]
    assert queues[0].priority_factor == 5


async def test_delete_queue(armada_credentials, mock_armada_client):
    await delete_queue.fn(armada_credentials=armada_credentials, name="test-queue")

    assert mock_armada_client.delete_queue.call_args[1] == {"name": "test-queue"}


async def test_get_queue(armada_credentials, mock_armada_client):
    mock_armada_client.get_queue.return_value = submit_pb2.Queue(name="test-queue")

    queue = await get_queue.fn(armada_credentials=armada_credentials, name="test-queue")

    assert queue.name == "test-queue"
    assert mock_armada_client.get_queue.call_args[1] == {"name": "test-queue"}


async def test_get_queues(armada_credentials, mock_armada_client):
    mock_armada_client.get_queues.return_value = [
        submit_pb2.Queue(name="a"),
        submit_pb2.Queue(name="b"),
    ]

    queues = await get_queues.fn(armada_credentials=armada_credentials)

    assert [queue.name for queue in queues] == ["a", "b"]
