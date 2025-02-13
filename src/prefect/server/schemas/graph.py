from typing import Any, List, Literal, Optional, Tuple
from uuid import UUID

from prefect.server.schemas.states import StateType
from prefect.server.utilities.schemas import PrefectBaseModel
from prefect.types._datetime import DateTime


class GraphState(PrefectBaseModel):
    id: UUID
    timestamp: DateTime
    type: StateType
    name: str


class GraphArtifact(PrefectBaseModel):
    id: UUID
    created: DateTime
    key: Optional[str]
    type: Optional[str]
    is_latest: bool
    data: Optional[Any]  # we only return data for progress artifacts for now


class Edge(PrefectBaseModel):
    id: UUID


class Node(PrefectBaseModel):
    kind: Literal["flow-run", "task-run"]
    id: UUID
    label: str
    state_type: StateType
    start_time: DateTime
    end_time: Optional[DateTime]
    parents: List[Edge]
    children: List[Edge]
    encapsulating: List[Edge]
    artifacts: List[GraphArtifact]


class Graph(PrefectBaseModel):
    start_time: Optional[DateTime]
    end_time: Optional[DateTime]
    root_node_ids: List[UUID]
    nodes: List[Tuple[UUID, Node]]
    artifacts: List[GraphArtifact]
    states: List[GraphState]
