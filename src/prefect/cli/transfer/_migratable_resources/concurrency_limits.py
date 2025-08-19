from __future__ import annotations

import uuid

from typing_extensions import Self

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.base import (
    MigratableProtocol,
    MigratableResource,
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    GlobalConcurrencyLimitCreate,
)
from prefect.client.schemas.responses import (
    GlobalConcurrencyLimitResponse,
)
from prefect.exceptions import (
    ObjectAlreadyExists,
)


class MigratableGlobalConcurrencyLimit(
    MigratableResource[GlobalConcurrencyLimitResponse]
):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, global_concurrency_limit: GlobalConcurrencyLimitResponse):
        self.source_global_concurrency_limit = global_concurrency_limit
        self.destination_global_concurrency_limit: (
            GlobalConcurrencyLimitResponse | None
        ) = None

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_global_concurrency_limit.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return (
            self.destination_global_concurrency_limit.id
            if self.destination_global_concurrency_limit
            else None
        )

    @classmethod
    async def construct(cls, obj: GlobalConcurrencyLimitResponse) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[GlobalConcurrencyLimitResponse] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []

    async def migrate(self) -> None:
        async with get_client() as client:
            try:
                await client.create_global_concurrency_limit(
                    concurrency_limit=GlobalConcurrencyLimitCreate(
                        name=self.source_global_concurrency_limit.name,
                        limit=self.source_global_concurrency_limit.limit,
                        active=self.source_global_concurrency_limit.active,
                        active_slots=self.source_global_concurrency_limit.active_slots,
                    ),
                )
                self.destination_global_concurrency_limit = (
                    await client.read_global_concurrency_limit_by_name(
                        self.source_global_concurrency_limit.name
                    )
                )
            except ObjectAlreadyExists:
                self.destination_global_concurrency_limit = (
                    await client.read_global_concurrency_limit_by_name(
                        self.source_global_concurrency_limit.name
                    )
                )
                raise TransferSkipped("Already exists")
