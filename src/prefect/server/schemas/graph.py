from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from prefect.server.schemas.states import StateType
from prefect.server.utilities.schemas import PrefectBaseModel


class GraphState(PrefectBaseModel):
    id: UUID
    timestamp: datetime
    type: StateType
    name: str


class GraphArtifact(PrefectBaseModel):
    id: UUID
    created: datetime
    key: Optional[str]
    type: str
    is_latest: bool
    data: Optional[Any]  # we only return data for progress artifacts for now


class Edge(PrefectBaseModel):
    id: UUID


class Node(PrefectBaseModel):
    kind: Literal["flow-run", "task-run"]
    id: UUID
    label: str
    state_type: StateType
    start_time: datetime
    end_time: Optional[datetime]
    parents: list[Edge]
    children: list[Edge]
    encapsulating: list[Edge]
    artifacts: list[GraphArtifact]


class Graph(PrefectBaseModel):
    start_time: datetime
    end_time: Optional[datetime]
    root_node_ids: list[UUID]
    nodes: list[tuple[UUID, Node]]
    artifacts: list[GraphArtifact]
    states: list[GraphState]
