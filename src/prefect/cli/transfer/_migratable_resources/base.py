from __future__ import annotations

import abc
import uuid
from typing import Generic, Protocol, TypeVar, Union

from prefect.client.schemas.objects import (
    BlockDocument,
    BlockSchema,
    BlockType,
    Flow,
    Variable,
    WorkPool,
    WorkQueue,
)
from prefect.client.schemas.responses import (
    DeploymentResponse,
    GlobalConcurrencyLimitResponse,
)
from prefect.events.schemas.automations import Automation

MigratableType = Union[
    WorkPool,
    WorkQueue,
    DeploymentResponse,
    Flow,
    BlockType,
    BlockSchema,
    BlockDocument,
    Automation,
    GlobalConcurrencyLimitResponse,
    Variable,
]

T = TypeVar("T", bound=MigratableType)


class MigratableProtocol(Protocol):
    @property
    def source_id(self) -> uuid.UUID: ...

    @property
    def destination_id(self) -> uuid.UUID | None: ...

    async def get_dependencies(self) -> list["MigratableProtocol"]: ...
    async def migrate(self) -> None: ...


class MigratableResource(Generic[T], abc.ABC):
    @property
    @abc.abstractmethod
    def source_id(self) -> uuid.UUID: ...

    @property
    @abc.abstractmethod
    def destination_id(self) -> uuid.UUID | None: ...

    # Using this construct method because we may want to persist a serialized version of the object
    # to disk and reload it later to avoid using too much memory.
    @classmethod
    @abc.abstractmethod
    async def construct(cls, obj: T) -> "MigratableResource[T]": ...

    @abc.abstractmethod
    async def get_dependencies(self) -> "list[MigratableProtocol]": ...

    @classmethod
    @abc.abstractmethod
    async def get_instance(cls, id: uuid.UUID) -> "MigratableResource[T] | None": ...

    @abc.abstractmethod
    async def migrate(self) -> None: ...

    def __str__(self) -> str:
        return f"{type(self).__name__}(source_id={self.source_id})"
