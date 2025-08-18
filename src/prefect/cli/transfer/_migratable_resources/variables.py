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
    VariableCreate,
)
from prefect.client.schemas.objects import (
    Variable,
)
from prefect.exceptions import (
    ObjectAlreadyExists,
)


class MigratableVariable(MigratableResource[Variable]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, variable: Variable):
        self.source_variable = variable
        self.destination_variable: Variable | None = None

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_variable.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_variable.id if self.destination_variable else None

    @classmethod
    async def construct(cls, obj: Variable) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(cls, id: uuid.UUID) -> "MigratableResource[Variable] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []

    async def migrate(self) -> None:
        async with get_client() as client:
            try:
                self.destination_variable = await client.create_variable(
                    variable=VariableCreate(
                        name=self.source_variable.name,
                        value=self.source_variable.value,
                        tags=self.source_variable.tags,
                    ),
                )
            except ObjectAlreadyExists:
                self.destination_variable = await client.read_variable_by_name(
                    self.source_variable.name
                )
                raise TransferSkipped("Already exists")
