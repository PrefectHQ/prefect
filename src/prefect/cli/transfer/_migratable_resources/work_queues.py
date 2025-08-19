from __future__ import annotations

import uuid

from typing_extensions import Self

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources import construct_migratable_resource
from prefect.cli.transfer._migratable_resources.base import (
    MigratableProtocol,
    MigratableResource,
)
from prefect.cli.transfer._migratable_resources.work_pools import MigratableWorkPool
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName
from prefect.client.schemas.objects import (
    WorkQueue,
)
from prefect.exceptions import (
    ObjectAlreadyExists,
)


class MigratableWorkQueue(MigratableResource[WorkQueue]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, work_queue: WorkQueue):
        self.source_work_queue = work_queue
        self.destination_work_queue: WorkQueue | None = None
        self._dependencies: list[MigratableProtocol] = []

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_work_queue.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_work_queue.id if self.destination_work_queue else None

    @classmethod
    async def construct(cls, obj: WorkQueue) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[WorkQueue] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return self._dependencies

        async with get_client() as client:
            if self.source_work_queue.work_pool_name is not None:
                if dependency := await MigratableWorkPool.get_instance_by_name(
                    name=self.source_work_queue.work_pool_name
                ):
                    # Always include the pool as a dependency
                    # If it's push/managed, it will be skipped and this queue will be skipped too
                    self._dependencies.append(dependency)
                else:
                    work_pool = await client.read_work_pool(
                        self.source_work_queue.work_pool_name
                    )
                    self._dependencies.append(
                        await construct_migratable_resource(work_pool)
                    )

        return self._dependencies

    async def migrate(self) -> None:
        async with get_client() as client:
            # Skip default work queues as they are created when work pools are transferred
            if self.source_work_queue.name == "default":
                work_queues = await client.read_work_queues(
                    work_pool_name=self.source_work_queue.work_pool_name,
                    work_queue_filter=WorkQueueFilter(
                        name=WorkQueueFilterName(any_=["default"]),
                    ),
                )
                raise TransferSkipped("Default work queues are created with work pools")

            try:
                self.destination_work_queue = await client.create_work_queue(
                    name=self.source_work_queue.name,
                    description=self.source_work_queue.description,
                    priority=self.source_work_queue.priority,
                    concurrency_limit=self.source_work_queue.concurrency_limit,
                    work_pool_name=self.source_work_queue.work_pool_name,
                )
            except ObjectAlreadyExists:
                # Work queue already exists, read it by work pool and name
                work_queues = await client.read_work_queues(
                    work_pool_name=self.source_work_queue.work_pool_name,
                    work_queue_filter=WorkQueueFilter(
                        name=WorkQueueFilterName(any_=[self.source_work_queue.name]),
                    ),
                )
                if work_queues:
                    self.destination_work_queue = work_queues[0]
                    raise TransferSkipped("Already exists")
                else:
                    raise RuntimeError(
                        "Transfer failed due to conflict, but no existing queue found."
                    )
