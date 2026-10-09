"""Module to define tasks for interacting with Armada queues."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from armada_client.armada import submit_pb2
from armada_client.permissions import Permissions

from prefect import task
from prefect_armada.credentials import ArmadaCredentials
from prefect_armada.utilities import coerce_queues


def _build_queue(
    name: str,
    priority_factor: float | None = None,
    user_owners: list[str] | None = None,
    group_owners: list[str] | None = None,
    resource_limits: dict[str, float] | None = None,
    permissions: list[Permissions] | None = None,
) -> submit_pb2.Queue:
    """Builds an Armada `Queue` message from its component parts."""
    return submit_pb2.Queue(
        name=name,
        priority_factor=1.0 if priority_factor is None else priority_factor,
        user_owners=user_owners,
        group_owners=group_owners,
        resource_limits=resource_limits,
        permissions=[p.to_grpc() for p in permissions] if permissions else None,
    )


@task
async def create_queue(
    armada_credentials: ArmadaCredentials,
    name: str,
    priority_factor: float | None = None,
    user_owners: list[str] | None = None,
    group_owners: list[str] | None = None,
    resource_limits: dict[str, float] | None = None,
    permissions: list[Permissions] | None = None,
) -> Any:
    """Task for creating an Armada queue.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        name: The name of the queue to create.
        priority_factor: The priority factor for the queue. Defaults to `1.0`.
        user_owners: The users that own the queue.
        group_owners: The groups that own the queue.
        resource_limits: The fraction of cluster resources the queue may use,
            keyed by resource name.
        permissions: The permissions to grant on the queue.

    Returns:
        An empty response.

    Example:
        Create a queue for Prefect flow runs:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import create_queue

        @flow
        def armada_orchestrator():
            create_queue(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                name="prefect",
                priority_factor=1,
            )
        ```
    """
    queue = _build_queue(
        name=name,
        priority_factor=priority_factor,
        user_owners=user_owners,
        group_owners=group_owners,
        resource_limits=resource_limits,
        permissions=permissions,
    )
    async with armada_credentials.get_client() as client:
        return await client.create_queue(queue)


@task
async def update_queue(
    armada_credentials: ArmadaCredentials,
    name: str,
    priority_factor: float | None = None,
    user_owners: list[str] | None = None,
    group_owners: list[str] | None = None,
    resource_limits: dict[str, float] | None = None,
    permissions: list[Permissions] | None = None,
) -> Any:
    """Task for updating an Armada queue.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        name: The name of the queue to update.
        priority_factor: The priority factor for the queue. Defaults to `1.0`.
        user_owners: The users that own the queue.
        group_owners: The groups that own the queue.
        resource_limits: The fraction of cluster resources the queue may use,
            keyed by resource name.
        permissions: The permissions to grant on the queue.

    Returns:
        An empty response.

    Example:
        Raise the priority factor of a queue:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import update_queue

        @flow
        def armada_orchestrator():
            update_queue(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                name="prefect",
                priority_factor=2,
            )
        ```
    """
    queue = _build_queue(
        name=name,
        priority_factor=priority_factor,
        user_owners=user_owners,
        group_owners=group_owners,
        resource_limits=resource_limits,
        permissions=permissions,
    )
    async with armada_credentials.get_client() as client:
        return await client.update_queue(queue)


@task
async def create_queues(
    armada_credentials: ArmadaCredentials,
    queues: Sequence[dict[str, Any] | submit_pb2.Queue],
) -> submit_pb2.BatchQueueCreateResponse:
    """Task for creating several Armada queues at once.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queues: The queues to create, each given as a dictionary or an Armada
            `Queue` message.

    Returns:
        An Armada `BatchQueueCreateResponse` object.

    Example:
        Create two queues:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import create_queues

        @flow
        def armada_orchestrator():
            response = create_queues(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queues=[
                    {"name": "prefect", "priorityFactor": 1},
                    {"name": "prefect-batch", "priorityFactor": 2},
                ],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.create_queues(coerce_queues(queues))


@task
async def update_queues(
    armada_credentials: ArmadaCredentials,
    queues: Sequence[dict[str, Any] | submit_pb2.Queue],
) -> submit_pb2.BatchQueueUpdateResponse:
    """Task for updating several Armada queues at once.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        queues: The queues to update, each given as a dictionary or an Armada
            `Queue` message.

    Returns:
        An Armada `BatchQueueUpdateResponse` object.

    Example:
        Update two queues:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import update_queues

        @flow
        def armada_orchestrator():
            response = update_queues(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                queues=[
                    {"name": "prefect", "priorityFactor": 2},
                    {"name": "prefect-batch", "priorityFactor": 3},
                ],
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.update_queues(coerce_queues(queues))


@task
async def delete_queue(
    armada_credentials: ArmadaCredentials,
    name: str,
) -> None:
    """Task for deleting an empty Armada queue.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        name: The name of the empty queue to delete.

    Returns:
        `None`.

    Example:
        Delete a queue:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import delete_queue

        @flow
        def armada_orchestrator():
            delete_queue(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                name="prefect",
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.delete_queue(name=name)


@task
async def get_queue(
    armada_credentials: ArmadaCredentials,
    name: str,
) -> submit_pb2.Queue:
    """Task for reading an Armada queue.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.
        name: The name of the queue to read.

    Returns:
        An Armada `Queue` object.

    Example:
        Read a queue:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import get_queue

        @flow
        def armada_orchestrator():
            queue = get_queue(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
                name="prefect",
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_queue(name=name)


@task
async def get_queues(
    armada_credentials: ArmadaCredentials,
) -> list[submit_pb2.Queue]:
    """Task for listing every Armada queue.

    Args:
        armada_credentials: `ArmadaCredentials` block holding authentication
            needed to generate the required API client.

    Returns:
        A list of Armada `Queue` objects.

    Example:
        List all queues:
        ```python
        from prefect import flow
        from prefect_armada.credentials import ArmadaCredentials
        from prefect_armada.queues import get_queues

        @flow
        def armada_orchestrator():
            queues = get_queues(
                armada_credentials=ArmadaCredentials.load("armada-creds"),
            )
        ```
    """
    async with armada_credentials.get_client() as client:
        return await client.get_queues()
