from __future__ import annotations

import uuid

from typing_extensions import Self

from prefect.cli.transfer._exceptions import TransferSkipped
from prefect.cli.transfer._migratable_resources.base import (
    MigratableProtocol,
    MigratableResource,
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import FlowCreate
from prefect.client.schemas.filters import FlowFilter, FlowFilterName
from prefect.client.schemas.objects import Flow
from prefect.exceptions import (
    ObjectAlreadyExists,
)


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
                flows = await client.read_flows(
                    flow_filter=FlowFilter(
                        name=FlowFilterName(any_=[self.source_flow.name])
                    )
                )
                if flows and len(flows) == 1:
                    self.destination_flow = flows[0]
                else:
                    raise RuntimeError("Unable to find destination flow")
                raise TransferSkipped("Already exists")
