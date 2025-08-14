import abc
import uuid
from typing import Generic, Protocol, Self, TypeVar, overload

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import (
    BlockDocument,
    BlockSchema,
    BlockType,
    Deployment,
    Flow,
    GlobalConcurrencyLimit,
    Variable,
    WorkPool,
    WorkQueue,
)
from prefect.events.schemas.automations import Automation

MigratableType = (
    WorkPool
    | WorkQueue
    | Deployment
    | Flow
    | BlockType
    | BlockSchema
    | BlockDocument
    | Automation
    | GlobalConcurrencyLimit
    | Variable
)

T = TypeVar("T", bound=MigratableType)


class MigratableProtocol(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    async def get_dependencies(self) -> list["MigratableProtocol"]: ...


class MigratableResource(Generic[T], abc.ABC):
    @property
    @abc.abstractmethod
    def id(self) -> uuid.UUID: ...

    # Using this construct method because we may want to persist a serialized version of the object
    # to disk and reload it later to avoid using too much memory.
    @classmethod
    @abc.abstractmethod
    async def construct(cls, obj: T) -> "MigratableResource[T]": ...

    @abc.abstractmethod
    async def get_dependencies(self) -> "list[MigratableProtocol]": ...


class MigratableWorkPool(MigratableResource[WorkPool]):
    def __init__(self, obj: WorkPool):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: WorkPool) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableWorkQueue(MigratableResource[WorkQueue]):
    def __init__(self, obj: WorkQueue):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: WorkQueue) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        async with get_client() as client:
            if self.obj.work_pool_name is None:
                return []
            work_pool = await client.read_work_pool(self.obj.work_pool_name)
            return [await construct_migratable_resource(work_pool)]


class MigratableDeployment(MigratableResource[Deployment]):
    def __init__(self, obj: Deployment):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: Deployment) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableFlow(MigratableResource[Flow]):
    def __init__(self, obj: Flow):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: Flow) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableBlockType(MigratableResource[BlockType]):
    def __init__(self, obj: BlockType):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: BlockType) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableBlockSchema(MigratableResource[BlockSchema]):
    def __init__(self, obj: BlockSchema):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: BlockSchema) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableBlockDocument(MigratableResource[BlockDocument]):
    def __init__(self, obj: BlockDocument):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: BlockDocument) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableAutomation(MigratableResource[Automation]):
    def __init__(self, obj: Automation):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: Automation) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableGlobalConcurrencyLimit(MigratableResource[GlobalConcurrencyLimit]):
    def __init__(self, obj: GlobalConcurrencyLimit):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: GlobalConcurrencyLimit) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


class MigratableVariable(MigratableResource[Variable]):
    def __init__(self, obj: Variable):
        self.obj = obj

    @property
    def id(self) -> uuid.UUID:
        return self.obj.id

    @classmethod
    async def construct(cls, obj: Variable) -> Self:
        return cls(obj)

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []


@overload
async def construct_migratable_resource(obj: WorkPool) -> MigratableWorkPool: ...
@overload
async def construct_migratable_resource(obj: WorkQueue) -> MigratableWorkQueue: ...
@overload
async def construct_migratable_resource(obj: Deployment) -> MigratableDeployment: ...
@overload
async def construct_migratable_resource(obj: Flow) -> MigratableFlow: ...
@overload
async def construct_migratable_resource(obj: BlockType) -> MigratableBlockType: ...
@overload
async def construct_migratable_resource(obj: BlockSchema) -> MigratableBlockSchema: ...
@overload
async def construct_migratable_resource(
    obj: BlockDocument,
) -> MigratableBlockDocument: ...
@overload
async def construct_migratable_resource(obj: Automation) -> MigratableAutomation: ...
@overload
async def construct_migratable_resource(
    obj: GlobalConcurrencyLimit,
) -> MigratableGlobalConcurrencyLimit: ...
@overload
async def construct_migratable_resource(obj: Variable) -> MigratableVariable: ...


async def construct_migratable_resource(
    obj: MigratableType,
) -> MigratableProtocol:
    if isinstance(obj, WorkPool):
        return await MigratableWorkPool.construct(obj)
    elif isinstance(obj, WorkQueue):
        return await MigratableWorkQueue.construct(obj)
    elif isinstance(obj, Deployment):
        return await MigratableDeployment.construct(obj)
    elif isinstance(obj, Flow):
        return await MigratableFlow.construct(obj)
    elif isinstance(obj, BlockType):
        return await MigratableBlockType.construct(obj)
    elif isinstance(obj, BlockSchema):
        return await MigratableBlockSchema.construct(obj)
    elif isinstance(obj, BlockDocument):
        return await MigratableBlockDocument.construct(obj)
    elif isinstance(obj, Automation):
        return await MigratableAutomation.construct(obj)
    elif isinstance(obj, GlobalConcurrencyLimit):
        return await MigratableGlobalConcurrencyLimit.construct(obj)
    else:
        return await MigratableVariable.construct(obj)
