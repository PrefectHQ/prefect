from __future__ import annotations

import abc
import uuid
from typing import Any, Generic, Protocol, TypeVar, Union, overload

from typing_extensions import Self

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import (
    BlockDocumentCreate,
    BlockSchemaCreate,
    BlockTypeCreate,
    DeploymentScheduleCreate,
    FlowCreate,
    GlobalConcurrencyLimitCreate,
    VariableCreate,
    WorkPoolCreate,
)
from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterId
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
from prefect.events.actions import (
    AutomationAction,
    CallWebhook,
    DeploymentAction,
    SendNotification,
    WorkPoolAction,
    WorkQueueAction,
)
from prefect.events.schemas.automations import Automation
from prefect.exceptions import ObjectAlreadyExists, PrefectHTTPStatusError

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
                raise RuntimeError("Skipped managed pool (cloud-specific)")

            # Allow push pools only if destination is Cloud
            if self.source_work_pool.is_push_pool:
                from prefect.client.base import ServerType

                if client.server_type != ServerType.CLOUD:
                    raise RuntimeError("Skipped push pool (requires Prefect Cloud)")
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
            except PrefectHTTPStatusError as e:
                if e.response.status_code == 403 and "plan does not support" in str(e):
                    raise RuntimeError(
                        "Skipped - destination requires Standard/Pro tier"
                    )
                elif e.response.status_code == 409:  # Conflict - already exists
                    self.destination_work_pool = await client.read_work_pool(
                        self.source_work_pool.name
                    )
                    raise RuntimeError("Skipped - already exists")
                else:
                    raise
            except ObjectAlreadyExists:
                self.destination_work_pool = await client.read_work_pool(
                    self.source_work_pool.name
                )
                raise RuntimeError("Skipped - already exists")

            # Update the default queue after successful creation
            await client.update_work_queue(
                id=self.destination_work_pool.default_queue_id,
                description=self.source_default_queue.description,
                priority=self.source_default_queue.priority,
                filter=self.source_default_queue.filter,
                concurrency_limit=self.source_default_queue.concurrency_limit,
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
                    work_pool_name=self.source_work_queue.work_pool_name
                )
                for queue in work_queues:
                    if queue.name == self.source_work_queue.name:
                        self.destination_work_queue = queue
                        break
                raise RuntimeError("Skipped - already exists")


class MigratableDeployment(MigratableResource[DeploymentResponse]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, deployment: DeploymentResponse):
        self.source_deployment = deployment
        self.destination_deployment: DeploymentResponse | None = None
        self._dependencies: dict[uuid.UUID, MigratableProtocol] = {}

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_deployment.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_deployment.id if self.destination_deployment else None

    @classmethod
    async def construct(cls, obj: DeploymentResponse) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[DeploymentResponse] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return list(self._dependencies.values())

        async with get_client() as client:
            if dependency := await MigratableFlow.get_instance(
                id=self.source_deployment.flow_id
            ):
                self._dependencies[self.source_deployment.flow_id] = dependency
            else:
                flow = await client.read_flow(self.source_deployment.flow_id)
                self._dependencies[
                    self.source_deployment.flow_id
                ] = await construct_migratable_resource(flow)
            if self.source_deployment.work_queue_id is not None:
                if dependency := await MigratableWorkQueue.get_instance(
                    id=self.source_deployment.work_queue_id
                ):
                    self._dependencies[self.source_deployment.work_queue_id] = (
                        dependency
                    )
                else:
                    work_queue = await client.read_work_queue(
                        self.source_deployment.work_queue_id
                    )
                    self._dependencies[
                        work_queue.id
                    ] = await construct_migratable_resource(work_queue)
            if self.source_deployment.storage_document_id is not None:
                if dependency := await MigratableBlockDocument.get_instance(
                    id=self.source_deployment.storage_document_id
                ):
                    self._dependencies[self.source_deployment.storage_document_id] = (
                        dependency
                    )
                else:
                    storage_document = await client.read_block_document(
                        self.source_deployment.storage_document_id
                    )
                    self._dependencies[
                        storage_document.id
                    ] = await construct_migratable_resource(storage_document)
            if self.source_deployment.infrastructure_document_id is not None:
                if dependency := await MigratableBlockDocument.get_instance(
                    id=self.source_deployment.infrastructure_document_id
                ):
                    self._dependencies[
                        self.source_deployment.infrastructure_document_id
                    ] = dependency
                else:
                    infrastructure_document = await client.read_block_document(
                        self.source_deployment.infrastructure_document_id
                    )
                    self._dependencies[
                        infrastructure_document.id
                    ] = await construct_migratable_resource(infrastructure_document)
            if self.source_deployment.pull_steps:
                # TODO: Figure out how to find block document references in pull steps
                pass

        return list(self._dependencies.values())

    async def migrate(self) -> None:
        async with get_client() as client:
            try:
                if (
                    destination_flow_id := getattr(
                        self._dependencies.get(self.source_deployment.flow_id),
                        "destination_id",
                        None,
                    )
                ) is None:
                    raise ValueError("Unable to find destination flow")
                if (
                    self.source_deployment.storage_document_id
                    and (
                        destination_storage_document_id := getattr(
                            self._dependencies.get(
                                self.source_deployment.storage_document_id
                            ),
                            "destination_id",
                            None,
                        )
                    )
                    is None
                ):
                    raise ValueError("Unable to find destination storage document")
                else:
                    destination_storage_document_id = None
                if (
                    self.source_deployment.infrastructure_document_id
                    and (
                        destination_infrastructure_document_id := getattr(
                            self._dependencies.get(
                                self.source_deployment.infrastructure_document_id
                            ),
                            "destination_id",
                            None,
                        )
                    )
                    is None
                ):
                    raise ValueError(
                        "Unable to find destination infrastructure document"
                    )
                else:
                    destination_infrastructure_document_id = None

                destination_deployment_id = await client.create_deployment(
                    flow_id=destination_flow_id,
                    name=self.source_deployment.name,
                    version=self.source_deployment.version,
                    version_info=self.source_deployment.version_info,
                    schedules=[
                        DeploymentScheduleCreate(
                            schedule=schedule.schedule,
                            active=schedule.active,
                            max_scheduled_runs=schedule.max_scheduled_runs,
                            parameters=schedule.parameters,
                            slug=schedule.slug,
                        )
                        for schedule in self.source_deployment.schedules
                    ],
                    concurrency_limit=self.source_deployment.concurrency_limit,
                    concurrency_options=self.source_deployment.concurrency_options,
                    parameters=self.source_deployment.parameters,
                    description=self.source_deployment.description,
                    work_queue_name=self.source_deployment.work_queue_name,
                    work_pool_name=self.source_deployment.work_pool_name,
                    tags=self.source_deployment.tags,
                    storage_document_id=destination_storage_document_id,
                    path=self.source_deployment.path,
                    entrypoint=self.source_deployment.entrypoint,
                    infrastructure_document_id=destination_infrastructure_document_id,
                    parameter_openapi_schema=self.source_deployment.parameter_openapi_schema,
                    paused=self.source_deployment.paused,
                    pull_steps=self.source_deployment.pull_steps,
                    enforce_parameter_schema=self.source_deployment.enforce_parameter_schema,
                    job_variables=self.source_deployment.job_variables,
                    branch=self.source_deployment.branch,
                    base=self.source_deployment.base,
                    root=self.source_deployment.root,
                )
                self.destination_deployment = await client.read_deployment(
                    destination_deployment_id
                )
            except PrefectHTTPStatusError as e:
                if (
                    e.response.status_code == 403
                    and "maximum number of deployments" in str(e)
                ):
                    raise RuntimeError(
                        "Skipped - deployment limit reached (upgrade tier)"
                    )
                elif e.response.status_code == 409:  # Conflict - already exists
                    self.destination_deployment = await client.read_deployment(
                        self.source_deployment.id
                    )
                    raise RuntimeError("Skipped - already exists")
                else:
                    raise
            except ObjectAlreadyExists:
                self.destination_deployment = await client.read_deployment(
                    self.source_deployment.id
                )
                raise RuntimeError("Skipped - already exists")


class MigratableFlow(MigratableResource[Flow]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, flow: Flow):
        self.source_flow = flow
        self.destination_flow: Flow | None = None

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_flow.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_flow.id if self.destination_flow else None

    @classmethod
    async def construct(cls, obj: Flow) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(cls, id: uuid.UUID) -> "MigratableResource[Flow] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []

    async def migrate(self) -> None:
        async with get_client() as client:
            try:
                flow_data = FlowCreate(
                    name=self.source_flow.name,
                    tags=self.source_flow.tags,
                    labels=self.source_flow.labels,
                )
                # We don't have a pre-built client method that accepts tags and labels
                response = await client.request(
                    "POST", "/flows/", json=flow_data.model_dump(mode="json")
                )
                self.destination_flow = Flow.model_validate(response.json())
            except ObjectAlreadyExists:
                # Flow already exists, read it by name
                flows = await client.read_flows()
                for flow in flows:
                    if flow.name == self.source_flow.name:
                        self.destination_flow = flow
                        break
                raise RuntimeError("Skipped - already exists")


class MigratableBlockType(MigratableResource[BlockType]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, block_type: BlockType):
        self.source_block_type = block_type
        self.destination_block_type: BlockType | None = None

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_block_type.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_block_type.id if self.destination_block_type else None

    @classmethod
    async def construct(cls, obj: BlockType) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[BlockType] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        return []

    async def migrate(self) -> None:
        async with get_client() as client:
            try:
                block_type = await client.create_block_type(
                    block_type=BlockTypeCreate(
                        name=self.source_block_type.name,
                        slug=self.source_block_type.slug,
                    ),
                )
                self.destination_block_type = block_type
            except ObjectAlreadyExists:
                self.destination_block_type = await client.read_block_type_by_slug(
                    self.source_block_type.slug
                )
                raise RuntimeError("Skipped - already exists")


class MigratableBlockSchema(MigratableResource[BlockSchema]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, block_schema: BlockSchema):
        self.source_block_schema = block_schema
        self.destination_block_schema: BlockSchema | None = None
        self._dependencies: dict[uuid.UUID, MigratableProtocol] = {}

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_block_schema.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return (
            self.destination_block_schema.id if self.destination_block_schema else None
        )

    @classmethod
    async def construct(cls, obj: BlockSchema) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[BlockSchema] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return list(self._dependencies.values())

        async with get_client() as client:
            if self.source_block_schema.block_type is not None:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_schema.block_type.id
                ):
                    self._dependencies[self.source_block_schema.block_type.id] = (
                        dependency
                    )
                else:
                    self._dependencies[
                        self.source_block_schema.block_type.id
                    ] = await construct_migratable_resource(
                        self.source_block_schema.block_type
                    )
            elif self.source_block_schema.block_type_id is not None:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_schema.block_type_id
                ):
                    self._dependencies[self.source_block_schema.block_type_id] = (
                        dependency
                    )
                else:
                    response = await client.request(
                        "GET",
                        "/block_types/{id}",
                        params={"id": self.source_block_schema.block_type_id},
                    )
                    block_type = BlockType.model_validate(response.json())
                    self._dependencies[
                        block_type.id
                    ] = await construct_migratable_resource(block_type)
            else:
                raise ValueError("Block schema has no associated block type")

            block_schema_references: dict[str, dict[str, Any]] = (
                self.source_block_schema.fields.get("block_schema_references", {})
            )
            for block_schema_reference in block_schema_references.values():
                if isinstance(block_schema_reference, list):
                    for block_schema_reference in block_schema_reference:
                        if block_schema_checksum := block_schema_reference.get(
                            "block_schema_checksum"
                        ):
                            block_schema = await client.read_block_schema_by_checksum(
                                block_schema_checksum
                            )
                            if dependency := await MigratableBlockSchema.get_instance(
                                id=block_schema.id
                            ):
                                self._dependencies[block_schema.id] = dependency
                            else:
                                self._dependencies[
                                    block_schema.id
                                ] = await construct_migratable_resource(block_schema)
                else:
                    if block_schema_checksum := block_schema_reference.get(
                        "block_schema_checksum"
                    ):
                        block_schema = await client.read_block_schema_by_checksum(
                            block_schema_checksum
                        )
                        if dependency := await MigratableBlockSchema.get_instance(
                            id=block_schema.id
                        ):
                            self._dependencies[block_schema.id] = dependency
                        else:
                            self._dependencies[
                                block_schema.id
                            ] = await construct_migratable_resource(block_schema)

        return list(self._dependencies.values())

    async def migrate(self) -> None:
        if self.source_block_schema.block_type_id is None:
            raise ValueError("Block schema has no associated block type")
        if (
            destination_block_type := self._dependencies.get(
                self.source_block_schema.block_type_id
            )
        ) is None:
            raise ValueError("Unable to find destination block type")
        async with get_client() as client:
            try:
                self.destination_block_schema = await client.create_block_schema(
                    block_schema=BlockSchemaCreate(
                        fields=self.source_block_schema.fields,
                        block_type_id=destination_block_type.destination_id,
                        capabilities=self.source_block_schema.capabilities,
                        version=self.source_block_schema.version,
                    ),
                )
            except ObjectAlreadyExists:
                self.destination_block_schema = (
                    await client.read_block_schema_by_checksum(
                        self.source_block_schema.checksum
                    )
                )
                raise RuntimeError("Skipped - already exists")


class MigratableBlockDocument(MigratableResource[BlockDocument]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, block_document: BlockDocument):
        self.source_block_document = block_document
        self.destination_block_document: BlockDocument | None = None
        self._dependencies: dict[uuid.UUID, MigratableProtocol] = {}

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_block_document.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return (
            self.destination_block_document.id
            if self.destination_block_document
            else None
        )

    @classmethod
    async def construct(cls, obj: BlockDocument) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[BlockDocument] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return list(self._dependencies.values())

        # TODO: When we write serialized versions of the objects to disk, we should have a way to
        # use a client, but read from disk if the object has already been fetched.
        async with get_client() as client:
            if self.source_block_document.block_type is not None:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_document.block_type.id
                ):
                    self._dependencies[self.source_block_document.block_type.id] = (
                        dependency
                    )
                else:
                    self._dependencies[
                        self.source_block_document.block_type.id
                    ] = await construct_migratable_resource(
                        self.source_block_document.block_type
                    )
            else:
                if dependency := await MigratableBlockType.get_instance(
                    id=self.source_block_document.block_type_id
                ):
                    self._dependencies[self.source_block_document.block_type_id] = (
                        dependency
                    )
                else:
                    response = await client.request(
                        "GET",
                        "/block_types/{id}",
                        params={"id": self.source_block_document.block_type_id},
                    )
                    block_type = BlockType.model_validate(response.json())
                    self._dependencies[
                        block_type.id
                    ] = await construct_migratable_resource(block_type)

            if self.source_block_document.block_schema is not None:
                if dependency := await MigratableBlockSchema.get_instance(
                    id=self.source_block_document.block_schema.id
                ):
                    self._dependencies[self.source_block_document.block_schema.id] = (
                        dependency
                    )
                else:
                    self._dependencies[
                        self.source_block_document.block_schema.id
                    ] = await construct_migratable_resource(
                        self.source_block_document.block_schema
                    )
            else:
                if dependency := await MigratableBlockSchema.get_instance(
                    id=self.source_block_document.block_schema_id
                ):
                    self._dependencies[self.source_block_document.block_schema_id] = (
                        dependency
                    )
                else:
                    response = await client.request(
                        "GET",
                        "/block_schemas/{id}",
                        params={"id": self.source_block_document.block_schema_id},
                    )
                    block_schema = BlockSchema.model_validate(response.json())
                    self._dependencies[
                        block_schema.id
                    ] = await construct_migratable_resource(block_schema)

            if self.source_block_document.block_document_references:
                for (
                    block_document_reference
                ) in self.source_block_document.block_document_references.values():
                    if block_document_id := block_document_reference.get(
                        "block_document_id"
                    ):
                        if dependency := await MigratableBlockDocument.get_instance(
                            id=block_document_id
                        ):
                            self._dependencies[block_document_id] = dependency
                        else:
                            block_document = await client.read_block_document(
                                block_document_id
                            )
                            self._dependencies[
                                block_document.id
                            ] = await construct_migratable_resource(block_document)

        return list(self._dependencies.values())

    async def migrate(self) -> None:
        if (
            destination_block_type := self._dependencies.get(
                self.source_block_document.block_type_id
            )
        ) is None or not destination_block_type.destination_id:
            raise ValueError("Unable to find destination block type")
        if (
            destination_block_schema := self._dependencies.get(
                self.source_block_document.block_schema_id
            )
        ) is None or not destination_block_schema.destination_id:
            raise ValueError("Unable to find destination block schema")

        async with get_client() as client:
            try:
                # TODO: Check if data needs to be written differently to maintain composition
                self.destination_block_document = await client.create_block_document(
                    block_document=BlockDocumentCreate(
                        name=self.source_block_document.name,
                        block_type_id=destination_block_type.destination_id,
                        block_schema_id=destination_block_schema.destination_id,
                        data=self.source_block_document.data,
                    ),
                )
            except ObjectAlreadyExists:
                if self.source_block_document.name is None:
                    # This is technically impossible, but our typing thinks it's possible
                    raise ValueError(
                        "Block document has no name, which should be impossible. "
                        "Please report this as a bug."
                    )

                if self.source_block_document.block_type is not None:
                    block_type_slug = self.source_block_document.block_type.slug
                else:
                    # TODO: Add real client methods for places where we use `client.request`
                    response = await client.request(
                        "GET",
                        "/block_types/{id}",
                        params={"id": self.source_block_document.block_type_id},
                    )
                    block_type = BlockType.model_validate(response.json())
                    block_type_slug = block_type.slug

                self.destination_block_document = (
                    await client.read_block_document_by_name(
                        block_type_slug=block_type_slug,
                        name=self.source_block_document.name,
                    )
                )
                raise RuntimeError("Skipped - already exists")


class MigratableAutomation(MigratableResource[Automation]):
    _instances: dict[uuid.UUID, Self] = {}

    def __init__(self, automation: Automation):
        self.source_automation = automation
        self.destination_automation: Automation | None = None
        self._dependencies: dict[uuid.UUID, MigratableProtocol] = {}

    @property
    def source_id(self) -> uuid.UUID:
        return self.source_automation.id

    @property
    def destination_id(self) -> uuid.UUID | None:
        return self.destination_automation.id if self.destination_automation else None

    @classmethod
    async def construct(cls, obj: Automation) -> Self:
        if obj.id in cls._instances:
            return cls._instances[obj.id]
        instance = cls(obj)
        cls._instances[obj.id] = instance
        return instance

    @classmethod
    async def get_instance(
        cls, id: uuid.UUID
    ) -> "MigratableResource[Automation] | None":
        if id in cls._instances:
            return cls._instances[id]
        return None

    async def get_dependencies(self) -> "list[MigratableProtocol]":
        if self._dependencies:
            return list(self._dependencies.values())

        async with get_client() as client:
            for action in self.source_automation.actions:
                if (
                    isinstance(action, DeploymentAction)
                    and action.deployment_id is not None
                ):
                    if dependency := await MigratableDeployment.get_instance(
                        id=action.deployment_id
                    ):
                        self._dependencies[action.deployment_id] = dependency
                    else:
                        deployment = await client.read_deployment(action.deployment_id)
                        self._dependencies[
                            deployment.id
                        ] = await construct_migratable_resource(deployment)
                elif (
                    isinstance(action, WorkPoolAction)
                    and action.work_pool_id is not None
                ):
                    # TODO: Find a better way to get a work pool by id
                    if dependency := await MigratableWorkPool.get_instance(
                        id=action.work_pool_id
                    ):
                        self._dependencies[action.work_pool_id] = dependency
                    else:
                        work_pool = await client.read_work_pools(
                            work_pool_filter=WorkPoolFilter(
                                id=WorkPoolFilterId(any_=[action.work_pool_id])
                            )
                        )
                        if work_pool:
                            self._dependencies[
                                work_pool[0].id
                            ] = await construct_migratable_resource(work_pool[0])
                elif (
                    isinstance(action, WorkQueueAction)
                    and action.work_queue_id is not None
                ):
                    if dependency := await MigratableWorkQueue.get_instance(
                        id=action.work_queue_id
                    ):
                        self._dependencies[action.work_queue_id] = dependency
                    else:
                        work_queue = await client.read_work_queue(action.work_queue_id)
                        self._dependencies[
                            work_queue.id
                        ] = await construct_migratable_resource(work_queue)
                elif (
                    isinstance(action, AutomationAction)
                    and action.automation_id is not None
                ):
                    if dependency := await MigratableAutomation.get_instance(
                        id=action.automation_id
                    ):
                        self._dependencies[action.automation_id] = dependency
                    else:
                        automation = await client.find_automation(action.automation_id)
                        if automation:
                            self._dependencies[
                                automation.id
                            ] = await construct_migratable_resource(automation)
                elif isinstance(action, CallWebhook):
                    if dependency := await MigratableBlockDocument.get_instance(
                        id=action.block_document_id
                    ):
                        self._dependencies[action.block_document_id] = dependency
                    else:
                        block_document = await client.read_block_document(
                            action.block_document_id
                        )
                        self._dependencies[
                            block_document.id
                        ] = await construct_migratable_resource(block_document)
                elif isinstance(action, SendNotification):
                    if dependency := await MigratableBlockDocument.get_instance(
                        id=action.block_document_id
                    ):
                        self._dependencies[action.block_document_id] = dependency
                    else:
                        block_document = await client.read_block_document(
                            action.block_document_id
                        )
                        self._dependencies[
                            block_document.id
                        ] = await construct_migratable_resource(block_document)
        return list(self._dependencies.values())

    async def migrate(self) -> None:
        async with get_client() as client:
            automations = await client.read_automations_by_name(
                name=self.source_automation.name
            )
            if automations:
                self.destination_automation = automations[0]
                raise RuntimeError("Skipped - already exists")
            else:
                automation_copy = self.source_automation.model_copy(deep=True)
                for action in automation_copy.actions:
                    if (
                        isinstance(action, DeploymentAction)
                        and action.deployment_id is not None
                    ):
                        action.deployment_id = self._dependencies[
                            action.deployment_id
                        ].destination_id
                    elif (
                        isinstance(action, WorkPoolAction)
                        and action.work_pool_id is not None
                    ):
                        action.work_pool_id = self._dependencies[
                            action.work_pool_id
                        ].destination_id
                    elif (
                        isinstance(action, WorkQueueAction)
                        and action.work_queue_id is not None
                    ):
                        action.work_queue_id = self._dependencies[
                            action.work_queue_id
                        ].destination_id
                    elif (
                        isinstance(action, AutomationAction)
                        and action.automation_id is not None
                    ):
                        action.automation_id = self._dependencies[
                            action.automation_id
                        ].destination_id
                    elif isinstance(action, CallWebhook):
                        if destination_block_document_id := getattr(
                            self._dependencies.get(action.block_document_id),
                            "destination_id",
                            None,
                        ):
                            action.block_document_id = destination_block_document_id
                    elif isinstance(action, SendNotification):
                        if destination_block_document_id := getattr(
                            self._dependencies.get(action.block_document_id),
                            "destination_id",
                            None,
                        ):
                            action.block_document_id = destination_block_document_id
                # Create automation without id field - the server will generate a new one
                automation_dict = automation_copy.model_dump(
                    mode="json", exclude={"id", "created", "updated"}
                )
                response = await client._client.post(
                    "/automations/", json=automation_dict
                )
                response.raise_for_status()
                result = response.json()
                self.destination_automation = await client.read_automation(result["id"])


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
            except PrefectHTTPStatusError as e:
                # 409 means it already exists, read the existing one
                if e.response.status_code == 409:
                    self.destination_global_concurrency_limit = (
                        await client.read_global_concurrency_limit_by_name(
                            self.source_global_concurrency_limit.name
                        )
                    )
                    raise RuntimeError("Skipped - already exists")
                else:
                    raise


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
            except PrefectHTTPStatusError as e:
                # 409 means it already exists, read the existing one
                if e.response.status_code == 409:
                    self.destination_variable = await client.read_variable_by_name(
                        self.source_variable.name
                    )
                    raise RuntimeError("Skipped - already exists")
                else:
                    raise


@overload
async def construct_migratable_resource(obj: WorkPool) -> MigratableWorkPool: ...
@overload
async def construct_migratable_resource(obj: WorkQueue) -> MigratableWorkQueue: ...
@overload
async def construct_migratable_resource(
    obj: DeploymentResponse,
) -> MigratableDeployment: ...
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
    obj: GlobalConcurrencyLimitResponse,
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
    elif isinstance(obj, DeploymentResponse):
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
    elif isinstance(obj, GlobalConcurrencyLimitResponse):
        return await MigratableGlobalConcurrencyLimit.construct(obj)
    else:
        return await MigratableVariable.construct(obj)
