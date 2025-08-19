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
from prefect.cli.transfer._migratable_resources.flows import MigratableFlow
from prefect.cli.transfer._migratable_resources.work_pools import MigratableWorkPool
from prefect.cli.transfer._migratable_resources.work_queues import MigratableWorkQueue
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.responses import DeploymentResponse
from prefect.exceptions import (
    ObjectAlreadyExists,
    ObjectLimitReached,
)


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
            if self.source_deployment.work_pool_name is not None:
                if dependency := await MigratableWorkPool.get_instance_by_name(
                    name=self.source_deployment.work_pool_name
                ):
                    self._dependencies[dependency.source_id] = dependency
                else:
                    work_pool = await client.read_work_pool(
                        self.source_deployment.work_pool_name
                    )
                    self._dependencies[
                        work_pool.id
                    ] = await construct_migratable_resource(work_pool)
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
            except ObjectLimitReached:
                raise TransferSkipped("Deployment limit reached (upgrade tier)")
            except ObjectAlreadyExists:
                self.destination_deployment = await client.read_deployment(
                    self.source_deployment.id
                )
                raise TransferSkipped("Already exists")
