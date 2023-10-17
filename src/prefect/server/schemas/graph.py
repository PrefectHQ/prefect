from datetime import datetime
from typing import List, Literal, Optional, Tuple
from uuid import UUID

from prefect.server.schemas.states import StateType
from prefect.server.utilities.schemas import PrefectBaseModel


class Edge(PrefectBaseModel):
    id: UUID


class Node(PrefectBaseModel):
    kind: Literal["flow-run", "task-run"]
    id: UUID
    label: str
    state_type: StateType
    state_name: str
    start_time: datetime
    end_time: Optional[datetime]
    parents: List[Edge]
    children: List[Edge]


class Graph(PrefectBaseModel):
    start_time: datetime
    end_time: Optional[datetime]
    root_node_ids: List[UUID]
    nodes: List[Tuple[UUID, Node]]
