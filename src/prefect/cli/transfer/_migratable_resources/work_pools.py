from __future__ import annotations

import uuid

from typing_extensions import Self

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources import construct_migratable_resource
from prefect.cli.transfer._migratable_resources.base import (
    MigratableProtocol,
    MigratableResource,
)
from prefect.cli.transfer._migratable_resources.blocks import MigratableBlockDocument
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    WorkPoolCreate,
)
from prefect.client.schemas.objects import (
    WorkPool,
    WorkQueue,
)
from prefect.exceptions import (
    ObjectAlreadyExists,
    ObjectUnsupported,
)


class MigratableWorkPool(MigratableResource[WorkPool]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, work_pool: WorkPool, default_queue: WorkQueue):
        self.source_work_pool = work_pool
        self.source_default_queue = default_queue
        self.destination_work_pool: WorkPool | None = None
        self._dependencies: list[MigratableProtocol] = []

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_work_pool.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_work_pool.id if self.destination_work_pool else None

    @classmethod
    async def construct(cls, obj: WorkPool) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        async with get_client() as client:
            default_queue = await client.read_work_queue(obj.default_queue_id)
            instance = cls(obj, default_queue)
            cls._instances[obj.id] = instance
            return instance

    @classmethod
    async def get_instance(cls, id: uuid.UUID) -> "MigratableResource[WorkPool] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    @classmethod
    async def get_instance_by_name(
        cls, name: str
    ) -> "MigratableResource[WorkPool] | None":
        for instance in cls._instances.values():
            if instance.source_work_pool.name == name:
                return instance
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return self._dependencies

        async with get_client() as client:
            if (
                self.source_work_pool.storage_configuration.default_result_storage_block_id
                is not None
            ):
                if dependency := await MigratableBlockDocument.get_instance(
                    id=self.source_work_pool.storage_configuration.default_result_storage_block_id
                ):
                    self._dependencies.append(dependency)
                else:
                    result_storage_block = await client.read_block_document(
                        self.source_work_pool.storage_configuration.default_result_storage_block_id
                    )
                    self._dependencies.append(
                        await construct_migratable_resource(result_storage_block)
                    )
            if (
                self.source_work_pool.storage_configuration.bundle_upload_step
                is not None
            ):
                # TODO: Figure out how to find block document references in bundle upload step
                pass
            if (
                self.source_work_pool.storage_configuration.bundle_execution_step
                is not None
            ):
                # TODO: Figure out how to find block document references in bundle download step
                pass
        return self._dependencies

    async def migrate(self) -> None:
        async with get_client() as client:
            # Skip managed pools always - they're cloud-specific infrastructure
            if self.source_work_pool.is_managed_pool:
                raise TransferSkipped("Skipped managed pool (cloud-specific)")

            # Allow push pools only if destination is Cloud
            if self.source_work_pool.is_push_pool:
                from prefect.client.base import ServerType

                if client.server_type != ServerType.CLOUD:
                    raise TransferSkipped("Skipped push pool (requires Prefect Cloud)")
            try:
                self.destination_work_pool = await client.create_work_pool(
                    work_pool=WorkPoolCreate(
                        name=self.source_work_pool.name,
                        type=self.source_work_pool.type,
                        base_job_template=self.source_work_pool.base_job_template,
                        is_paused=self.source_work_pool.is_paused,
                        concurrency_limit=self.source_work_pool.concurrency_limit,
                        storage_configuration=self.source_work_pool.storage_configuration,
                    ),
                )
            except ObjectUnsupported:
                raise TransferSkipped("Destination requires Standard/Pro tier")
            except ObjectAlreadyExists:
                self.destination_work_pool = await client.read_work_pool(
                    self.source_work_pool.name
                )
                raise TransferSkipped("Already exists")

            # Update the default queue after successful creation
            await client.update_work_queue(
                id=self.destination_work_pool.default_queue_id,
                description=self.source_default_queue.description,
                priority=self.source_default_queue.priority,
                concurrency_limit=self.source_default_queue.concurrency_limit,
            )
