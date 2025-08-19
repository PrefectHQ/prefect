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
from prefect.cli.transfer._migratable_resources.deployments import MigratableDeployment
from prefect.cli.transfer._migratable_resources.work_pools import MigratableWorkPool
from prefect.cli.transfer._migratable_resources.work_queues import MigratableWorkQueue
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    WorkPoolFilter,
    WorkPoolFilterId,
)
from prefect.events.actions import (
    AutomationAction,
    CallWebhook,
    DeploymentAction,
    SendNotification,
    WorkPoolAction,
    WorkQueueAction,
)
from prefect.events.schemas.automations import Automation, AutomationCore


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
                raise TransferSkipped("Already exists")
            else:
                automation_copy = AutomationCore.model_validate(
                    self.source_automation.model_dump(mode="json")
                )
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

                automation_id = await client.create_automation(
                    automation=automation_copy
                )
                self.destination_automation = await client.read_automation(
                    automation_id=automation_id
                )
