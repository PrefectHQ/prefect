from datetime import datetime
from typing import List, Literal, Optional, Tuple
from uuid import UUID

from pydantic import Field

from prefect.server.schemas.states import StateType
from prefect.server.utilities.schemas import PrefectBaseModel


class GraphArtifact(PrefectBaseModel):
    id: UUID
    created: datetime
    key: Optional[str]
    type: str
    is_latest: bool = Field(default=False)


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
    artifacts: List[GraphArtifact] = Field(default_factory=list)


class Graph(PrefectBaseModel):
    start_time: datetime
    end_time: Optional[datetime]
    root_node_ids: List[UUID]
    nodes: List[Tuple[UUID, Node]]
    artifacts: List[GraphArtifact] = Field(default_factory=list)
