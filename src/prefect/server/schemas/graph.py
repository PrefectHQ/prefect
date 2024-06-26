from datetime import datetime
from typing import Any, List, Literal, Optional, Tuple
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
    parents: List[Edge]
    children: List[Edge]
    encapsulating: List[Edge]
    artifacts: List[GraphArtifact]


class Graph(PrefectBaseModel):
    start_time: datetime
    end_time: Optional[datetime]
    root_node_ids: List[UUID]
    nodes: List[Tuple[UUID, Node]]
    artifacts: List[GraphArtifact]
    states: List[GraphState]
