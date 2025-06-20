import datetime
from collections import defaultdict
from operator import attrgetter
from typing import Iterable, List, Union
from unittest import mock
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface, orm_models
from prefect.server.exceptions import FlowRunGraphTooLarge, ObjectNotFoundError
from prefect.server.models.flow_runs import read_flow_run_graph
from prefect.server.schemas.graph import Edge, Graph, GraphArtifact, GraphState, Node
from prefect.server.schemas.states import StateType
from prefect.settings import (
    PREFECT_API_MAX_FLOW_RUN_GRAPH_ARTIFACTS,
    PREFECT_API_MAX_FLOW_RUN_GRAPH_NODES,
    temporary_settings,
)
from prefect.types._datetime import DateTime, earliest_possible_datetime, now


async def test_reading_graph_for_nonexistant_flow_run(
    session: AsyncSession,
):
    with pytest.raises(ObjectNotFoundError):
        await read_flow_run_graph(
            session=session,
            flow_run_id=uuid4(),
        )


def assert_graph_is_connected(graph: Graph, incremental: bool = False) -> None:
    """Things we expect to be true about the nodes of all graphs.  Some things may not
    be true of incremental graphs, so we may skip some tests"""
    nodes_by_id = {id: node for id, node in graph.nodes}

    def assert_ordered_by_start_time(items: Iterable[Union[Edge, Node]]) -> None:
        last_seen = DateTime(1978, 6, 4, tzinfo=ZoneInfo("UTC"))
        for item in items:
            try:
                node = nodes_by_id[item.id]
            except KeyError:
                if incremental:
                    continue
                raise

            assert node.start_time >= last_seen
            last_seen = node.start_time

    nodes = [node for _, node in graph.nodes]
    assert_ordered_by_start_time(nodes)

    for node in nodes:
        # all root nodes should be in the root_node_ids list of the graph
        if not node.parents:
            assert node.id in graph.root_node_ids

        # if I have parents, my parents should have a reference to me as a child
        for parent_edge in node.parents:
            try:
                parent_node = nodes_by_id[parent_edge.id]
            except KeyError:
                if incremental:
                    continue
                raise

            assert node.id in [child.id for child in parent_node.children]

        assert_ordered_by_start_time(node.parents)

        # if I have children, my children should have a reference to me as a parent
        for child_edge in node.children:
            try:
                child = nodes_by_id[child_edge.id]
            except KeyError:
                if incremental:
                    continue
                raise

            assert node.id in [parent.id for parent in child.parents]

        assert_ordered_by_start_time(node.children)


@pytest.fixture
def base_time(start_of_test: datetime.datetime) -> datetime.datetime:
    return start_of_test - datetime.timedelta(minutes=5)


@pytest.fixture
async def unstarted_flow_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow,  # : db.Flow,
    base_time: datetime.datetime,
):
    flow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow.id,
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time - datetime.timedelta(seconds=1),
        start_time=None,
        end_time=None,
    )
    session.add(flow_run)
    await session.commit()
    return flow_run


async def test_reading_graph_for_unstarted_flow_run_uses_expected_start_time(
    session: AsyncSession,
    unstarted_flow_run,  # db.FlowRun,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=unstarted_flow_run.id,
    )

    assert graph.start_time == unstarted_flow_run.expected_start_time
    assert graph.end_time == unstarted_flow_run.end_time
    assert graph.root_node_ids == []
    assert graph.nodes == []

    assert_graph_is_connected(graph)


@pytest.fixture
async def flow_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow,  # : db.Flow,
    base_time: datetime.datetime,
):
    flow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow.id,
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time - datetime.timedelta(seconds=1),
        start_time=base_time,
        end_time=base_time + datetime.timedelta(minutes=5),
    )
    session.add(flow_run)
    await session.commit()
    return flow_run


async def test_reading_graph_for_flow_run_with_no_tasks(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == []
    assert graph.nodes == []

    assert_graph_is_connected(graph)


async def test_reading_graph_for_flow_run_with_string_since_field(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
        since=earliest_possible_datetime(),
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == []
    assert graph.nodes == []


@pytest.fixture
async def flat_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: datetime.datetime,
):
    task_runs = [
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name=f"task-{i}",
            task_key=f"task-{i}",
            dynamic_key=f"task-{i}",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=i)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=i),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=i),
        )
        for i in range(5)
    ]
    session.add_all(task_runs)

    # mix in a PENDING task to show that it is excluded
    session.add(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-pending",
            task_key="task-pending",
            dynamic_key="task-pending",
            state_type=StateType.PENDING,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=3)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=3),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=3),
        )
    )

    # mix in a RUNNING task with no start_time to show that it is excluded
    session.add(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-running",
            task_key="task-running",
            dynamic_key="task-running",
            state_type=StateType.RUNNING,
            state_name="Irrelevant",
            expected_start_time=None,
            start_time=None,
            end_time=None,
        )
    )

    # turn the 3rd task into a Cached task, which needs to be treated specially
    # because Cached tasks are COMPLETED, but don't have start/end times, only
    # an expected_start_time
    task_runs[2].start_time = None
    task_runs[2].end_time = None
    task_runs[2].state_type = StateType.COMPLETED
    task_runs[2].state_name = "Cached"

    await session.commit()
    return task_runs


async def test_reading_graph_for_flow_run_with_flat_tasks(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    flat_tasks: List,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    # all of the task runs are root nodes since they have no data dependencies
    assert graph.root_node_ids == [task_run.id for task_run in flat_tasks]
    assert graph.nodes == [
        (
            task_run.id,
            Node(
                kind="task-run",
                id=task_run.id,
                label=task_run.name,
                state_type=task_run.state_type,
                start_time=(
                    task_run.expected_start_time
                    if (
                        task_run.state_type == StateType.COMPLETED
                        and not task_run.start_time
                    )
                    else task_run.start_time
                ),
                end_time=(
                    task_run.expected_start_time
                    if (
                        task_run.state_type == StateType.COMPLETED
                        and not task_run.end_time
                    )
                    else task_run.end_time
                ),
                parents=[],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        )
        for task_run in flat_tasks
    ]

    assert_graph_is_connected(graph)


@pytest.fixture
async def nested_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: DateTime,
) -> List:
    # This is a flow with 3 tasks. the flow calls task0.
    # task0 calls task1, and then passes its result to task2
    # flow
    #  └── task0
    #       └── task1 -> task2
    # NOTE: this graph is NOT connected, because task0 does not have any edges
    # it only encapsulates task1 and task2

    task_runs = []
    task_runs.append(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-0",
            task_key="task-0",
            dynamic_key="task-0",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=1)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=1),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=1),
            task_inputs={},
        )
    )

    task_runs.append(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-1",
            task_key="task-1",
            dynamic_key="task-1",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=2)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=2),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=2),
            task_inputs={
                "__parents__": [
                    {"id": task_runs[0].id, "input_type": "task_run"},
                ],
            },
        )
    )

    task_runs.append(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-2",
            task_key="task-2",
            dynamic_key="task-2",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=3)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=3),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=3),
            task_inputs={
                "x": [
                    {"id": task_runs[1].id, "input_type": "task_run"},
                ],
                "__parents__": [
                    {"id": task_runs[0].id, "input_type": "task_run"},
                ],
            },
        )
    )

    session.add_all(task_runs)
    await session.commit()
    return task_runs


async def test_reading_graph_for_flow_run_with_nested_tasks(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    nested_tasks: List,  # List[db.TaskRun],
    base_time: DateTime,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == [nested_tasks[0].id, nested_tasks[1].id]

    # This is a flow with 3 tasks. the flow calls task0.
    # task0 calls task1, and then passes its result to task2
    # flow
    #  └── task0
    #       └── task1 -> task2
    # NOTE: this graph is NOT connected, because task0 does not have any edges
    # it only encapsulates task1 and task2.

    assert graph.nodes == [
        (
            nested_tasks[0].id,
            Node(
                kind="task-run",
                id=nested_tasks[0].id,
                label="task-0",
                state_type=StateType.COMPLETED,
                start_time=nested_tasks[0].start_time,
                end_time=nested_tasks[0].end_time,
                parents=[],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            nested_tasks[1].id,
            Node(
                kind="task-run",
                id=nested_tasks[1].id,
                label="task-1",
                state_type=StateType.COMPLETED,
                start_time=nested_tasks[1].start_time,
                end_time=nested_tasks[1].end_time,
                parents=[],
                children=[
                    Edge(id=nested_tasks[2].id),
                ],
                encapsulating=[
                    Edge(id=nested_tasks[0].id),
                ],
                artifacts=[],
            ),
        ),
        (
            nested_tasks[2].id,
            Node(
                kind="task-run",
                id=nested_tasks[2].id,
                label="task-2",
                state_type=StateType.COMPLETED,
                start_time=nested_tasks[2].start_time,
                end_time=nested_tasks[2].end_time,
                parents=[
                    Edge(id=nested_tasks[1].id),
                ],
                children=[],
                encapsulating=[
                    Edge(id=nested_tasks[0].id),
                ],
                artifacts=[],
            ),
        ),
    ]


@pytest.fixture
async def nested_tasks_including_parent_with_multiple_params(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: DateTime,
) -> List:
    task_runs = []

    task_runs.append(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-0",
            task_key="task-0",
            dynamic_key="task-0",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=1)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=1),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=1),
            task_inputs={
                "first_arg": [],
                "second_arg": [],
            },
        )
    )

    task_runs.append(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-1",
            task_key="task-1",
            dynamic_key="task-1",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=2)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=2),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=2),
            task_inputs={
                "__parents__": [
                    {"id": task_runs[0].id, "input_type": "task_run"},
                ],
            },
        )
    )

    session.add_all(task_runs)
    await session.commit()
    return task_runs


async def test_reading_graph_nested_tasks_including_parent_with_multiple_params(
    session: AsyncSession,
    flow_run,
    nested_tasks_including_parent_with_multiple_params: List,
    base_time: DateTime,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    parent_task, child_task = nested_tasks_including_parent_with_multiple_params

    # Check that the encapsulating relationships are correct and deduplicated
    nodes_by_id = {node.id: node for _, node in graph.nodes}
    child_node = nodes_by_id[child_task.id]

    # Verify the child task has exactly one encapsulating reference to the parent
    assert len(child_node.encapsulating) == 1
    assert child_node.encapsulating[0].id == parent_task.id


@pytest.fixture
async def linked_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: DateTime,
) -> List:
    # The shape of this will be:
    # 4 top-level tasks
    # 2 tasks that each take two arguments from the top-level tasks
    # task-1 -|
    #         |-> task-5
    # task-2 -|
    # task-3 -|
    #         |-> task-6
    # task-4 -|

    task_runs = [
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name=f"task-{i}",
            task_key=f"task-{i}",
            dynamic_key=f"task-{i}",
            state_type=StateType.COMPLETED,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=i)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=i),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=i),
        )
        for i in range(4)
    ]

    index = len(task_runs)
    task_runs.extend(
        [
            db.TaskRun(
                id=uuid4(),
                flow_run_id=flow_run.id,
                name=f"task-{index + j}",
                task_key=f"task-{index + j}",
                dynamic_key=f"task-{index + j}",
                state_type=StateType.COMPLETED,
                state_name="Irrelevant",
                expected_start_time=base_time
                + datetime.timedelta(seconds=index + j)
                - datetime.timedelta(microseconds=1),
                start_time=base_time + datetime.timedelta(seconds=index + j),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=index + j),
                task_inputs={
                    "x": [
                        {"id": task_runs[2 * j].id, "input_type": "task_run"},
                    ],
                    "y": [
                        {"id": task_runs[2 * j + 1].id, "input_type": "task_run"},
                    ],
                },
            )
            for j in range(2)
        ]
    )

    session.add_all(task_runs)

    # mix in a PENDING task to show that it is excluded
    session.add(
        db.TaskRun(
            id=uuid4(),
            flow_run_id=flow_run.id,
            name="task-pending",
            task_key="task-pending",
            dynamic_key="task-pending",
            state_type=StateType.PENDING,
            state_name="Irrelevant",
            expected_start_time=base_time
            + datetime.timedelta(seconds=3)
            - datetime.timedelta(microseconds=1),
            start_time=base_time + datetime.timedelta(seconds=3),
            end_time=base_time + datetime.timedelta(minutes=1, seconds=3),
        )
    )

    await session.commit()
    return task_runs


async def test_reading_graph_for_flow_run_with_linked_tasks(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: DateTime,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == [task_run.id for task_run in linked_tasks[:4]]

    assert_graph_is_connected(graph)

    # The shape of this will be:
    # 4 top-level tasks
    # 2 tasks that each take two arguments from the top-level tasks
    # task-1 -|
    #         |-> task-5
    # task-2 -|
    # task-3 -|
    #         |-> task-6
    # task-4 -|
    assert graph.nodes == [
        (
            linked_tasks[0].id,
            Node(
                kind="task-run",
                id=linked_tasks[0].id,
                label="task-0",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=0),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=0),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[1].id,
            Node(
                kind="task-run",
                id=linked_tasks[1].id,
                label="task-1",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=1),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[2].id,
            Node(
                kind="task-run",
                id=linked_tasks[2].id,
                label="task-2",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=2),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=2),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[3].id,
            Node(
                kind="task-run",
                id=linked_tasks[3].id,
                label="task-3",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=3),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=3),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[4].id,
            Node(
                kind="task-run",
                id=linked_tasks[4].id,
                label="task-4",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=4),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=4),
                parents=[
                    Edge(id=linked_tasks[0].id),
                    Edge(id=linked_tasks[1].id),
                ],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[5].id,
            Node(
                kind="task-run",
                id=linked_tasks[5].id,
                label="task-5",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=5),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=5),
                parents=[
                    Edge(id=linked_tasks[2].id),
                    Edge(id=linked_tasks[3].id),
                ],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
    ]


async def test_reading_graph_for_flow_run_with_linked_unstarted_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: DateTime,
):
    await session.execute(
        sa.update(db.TaskRun)
        .where(db.TaskRun.id.in_([task_run.id for task_run in linked_tasks]))
        .values(start_time=None)
    )

    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == [task_run.id for task_run in linked_tasks[:4]]

    assert_graph_is_connected(graph)

    # The shape of this will be:
    # 4 top-level tasks
    # 2 tasks that each take two arguments from the top-level tasks
    # task-1 -|
    #         |-> task-5
    # task-2 -|
    # task-3 -|
    #         |-> task-6
    # task-4 -|
    assert graph.nodes == [
        (
            linked_tasks[0].id,
            Node(
                kind="task-run",
                id=linked_tasks[0].id,
                label="task-0",
                state_type=StateType.COMPLETED,
                start_time=base_time
                + datetime.timedelta(seconds=0)
                - datetime.timedelta(microseconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=0),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[1].id,
            Node(
                kind="task-run",
                id=linked_tasks[1].id,
                label="task-1",
                state_type=StateType.COMPLETED,
                start_time=base_time
                + datetime.timedelta(seconds=1)
                - datetime.timedelta(microseconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=1),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[2].id,
            Node(
                kind="task-run",
                id=linked_tasks[2].id,
                label="task-2",
                state_type=StateType.COMPLETED,
                start_time=base_time
                + datetime.timedelta(seconds=2)
                - datetime.timedelta(microseconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=2),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[3].id,
            Node(
                kind="task-run",
                id=linked_tasks[3].id,
                label="task-3",
                state_type=StateType.COMPLETED,
                start_time=base_time
                + datetime.timedelta(seconds=3)
                - datetime.timedelta(microseconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=3),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[4].id,
            Node(
                kind="task-run",
                id=linked_tasks[4].id,
                label="task-4",
                state_type=StateType.COMPLETED,
                start_time=base_time
                + datetime.timedelta(seconds=4)
                - datetime.timedelta(microseconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=4),
                parents=[
                    Edge(id=linked_tasks[0].id),
                    Edge(id=linked_tasks[1].id),
                ],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[5].id,
            Node(
                kind="task-run",
                id=linked_tasks[5].id,
                label="task-5",
                state_type=StateType.COMPLETED,
                start_time=base_time
                + datetime.timedelta(seconds=5)
                - datetime.timedelta(microseconds=1),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=5),
                parents=[
                    Edge(id=linked_tasks[2].id),
                    Edge(id=linked_tasks[3].id),
                ],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
    ]


async def test_reading_graph_for_flow_run_with_linked_tasks_incrementally(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: DateTime,
):
    # `since` is just after the second task ends, so we should only get the last four
    since = base_time + datetime.timedelta(minutes=1, seconds=1, microseconds=1000)
    assert linked_tasks[1].end_time
    assert linked_tasks[2].end_time
    assert linked_tasks[1].end_time < since < linked_tasks[2].end_time

    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
        since=since,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time

    assert graph.root_node_ids == [task_run.id for task_run in linked_tasks[2:4]]

    assert_graph_is_connected(graph, incremental=True)

    # The shape of this will be:
    # 4 top-level tasks
    # 2 tasks that each take two arguments from the top-level tasks
    # task-1 -|
    #         |-> task-5
    # task-2 -|
    # task-3 -|
    #         |-> task-6
    # task-4 -|
    #
    # This incremental request will be returning tasks 3, 4, 5, 6
    assert graph.nodes == [
        (
            linked_tasks[2].id,
            Node(
                kind="task-run",
                id=linked_tasks[2].id,
                label="task-2",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=2),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=2),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[3].id,
            Node(
                kind="task-run",
                id=linked_tasks[3].id,
                label="task-3",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=3),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=3),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[4].id,
            Node(
                kind="task-run",
                id=linked_tasks[4].id,
                label="task-4",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=4),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=4),
                parents=[
                    # important: these are not present in the node list because they
                    # already ended but we still have the edges referencing them
                    Edge(id=linked_tasks[0].id),
                    Edge(id=linked_tasks[1].id),
                ],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
        (
            linked_tasks[5].id,
            Node(
                kind="task-run",
                id=linked_tasks[5].id,
                label="task-5",
                state_type=StateType.COMPLETED,
                start_time=base_time + datetime.timedelta(seconds=5),
                end_time=base_time + datetime.timedelta(minutes=1, seconds=5),
                parents=[
                    Edge(id=linked_tasks[2].id),
                    Edge(id=linked_tasks[3].id),
                ],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        ),
    ]


@pytest.fixture
async def subflow_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: DateTime,
):
    wrapper_task = db.TaskRun(
        id=uuid4(),
        flow_run_id=flow_run.id,
        name="task-0",
        task_key="task-0",
        dynamic_key="task-0",
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time - datetime.timedelta(microseconds=1),
        start_time=base_time + datetime.timedelta(seconds=1),
        end_time=base_time + datetime.timedelta(minutes=1),
    )
    session.add(wrapper_task)
    await session.flush()

    subflow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow_run.flow_id,
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time - datetime.timedelta(microseconds=1),
        start_time=base_time,
        end_time=base_time + datetime.timedelta(minutes=5),
        parent_task_run_id=wrapper_task.id,
    )
    session.add(subflow_run)
    await session.commit()

    return subflow_run


async def test_reading_graph_with_subflow_run(
    session: AsyncSession,
    flow,  # db.Flow,
    flow_run,  # db.FlowRun,
    subflow_run,  # db.FlowRun,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == [subflow_run.id]

    assert_graph_is_connected(graph)

    assert graph.nodes == [
        (
            subflow_run.id,
            Node(
                kind="flow-run",
                id=subflow_run.id,
                label=f"{flow.name} / {subflow_run.name}",
                state_type=subflow_run.state_type,
                start_time=subflow_run.start_time,
                end_time=subflow_run.end_time,
                parents=[],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        )
    ]


async def test_reading_graph_with_unstarted_subflow_run(
    session: AsyncSession,
    db: PrefectDBInterface,
    flow,  # db.Flow,
    flow_run,  # db.FlowRun,
    subflow_run,  # db.FlowRun,
):
    await session.execute(
        sa.update(db.FlowRun)
        .where(db.FlowRun.id == subflow_run.id)
        .values(start_time=None)
    )

    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.start_time == flow_run.start_time
    assert graph.end_time == flow_run.end_time
    assert graph.root_node_ids == [subflow_run.id]

    assert_graph_is_connected(graph)

    assert graph.nodes == [
        (
            subflow_run.id,
            Node(
                kind="flow-run",
                id=subflow_run.id,
                label=f"{flow.name} / {subflow_run.name}",
                state_type=subflow_run.state_type,
                start_time=subflow_run.expected_start_time,
                end_time=subflow_run.end_time,
                parents=[],
                children=[],
                encapsulating=[],
                artifacts=[],
            ),
        )
    ]


async def test_state_types_are_true_state_type_enums(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    subflow_run,  # db.FlowRun,
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert len(graph.nodes)
    _, node = graph.nodes[0]

    assert isinstance(node.state_type, StateType)
    assert node.state_type == StateType.COMPLETED


@pytest.fixture
async def flow_run_artifacts(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
):  # -> tuple[db.Artifact, list[db.Artifact]]:
    """Create a flow run with related artifacts.
    Returns:
        tuple[orm.Artifact, list[orm.Artifact]]: The first item is the artifact
        that should be included in the graph. The second item is a list of artifacts
        that should be excluded from the graph.
    """
    artifact_no_key = db.Artifact(
        id=uuid4(),
        flow_run_id=flow_run.id,
        type="markdown",
        key=None,
    )

    # artifacts of type result should be excluded
    result_artifact = db.Artifact(
        id=uuid4(),
        flow_run_id=flow_run.id,
        type="result",
        key=None,
    )

    artifacts = [artifact_no_key, result_artifact]
    session.add_all(artifacts)
    await session.commit()

    return (artifact_no_key, artifacts[1:])


@pytest.fixture
async def flow_run_task_artifacts(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    flat_tasks,  # list[db.TaskRun],
):  # -> list[db.Artifact]:
    assert len(flat_tasks) >= 5, (
        "Setup error - this fixture expects to use at least 5 tasks"
    )

    task_artifact = db.Artifact(
        flow_run_id=flow_run.id,
        task_run_id=flat_tasks[0].id,
        type="markdown",
        key=None,
    )

    task_artifact_with_key_not_latest = await models.artifacts.create_artifact(
        session,
        schemas.core.Artifact(
            type="markdown",
            key="collection-key--not-latest",
            flow_run_id=flow_run.id,
            task_run_id=flat_tasks[1].id,
        ),
    )

    latest_in_key_collection_but_not_this_flow_run = (
        await models.artifacts.create_artifact(
            session,
            schemas.core.Artifact(
                type="markdown",
                key="collection-key--not-latest",
                flow_run_id=uuid4(),
                task_run_id=uuid4(),
            ),
        )
    )

    task_artifact_latest_in_collection = await models.artifacts.create_artifact(
        session,
        schemas.core.Artifact(
            type="markdown",
            key="collection-key--latest",
            flow_run_id=flow_run.id,
            task_run_id=flat_tasks[2].id,
        ),
    )

    task_link_artifact = db.Artifact(
        flow_run_id=flow_run.id,
        task_run_id=flat_tasks[3].id,
        type="link",
    )

    task_table_artifact = db.Artifact(
        flow_run_id=flow_run.id,
        task_run_id=flat_tasks[4].id,
        type="table",
        created=now("UTC") - datetime.timedelta(minutes=2),
    )

    # second artifact from same task with a different created time
    task_table_artifact_from_same_task = db.Artifact(
        flow_run_id=flow_run.id,
        task_run_id=flat_tasks[4].id,
        type="table",
        created=now("UTC") - datetime.timedelta(minutes=1),
    )

    result_type_artifact = db.Artifact(
        flow_run_id=flow_run.id,
        task_run_id=flat_tasks[1].id,
        type="result",
        key=None,
    )

    progress_type_artifact = db.Artifact(
        flow_run_id=flow_run.id,
        task_run_id=flat_tasks[0].id,
        type="progress",
        data=0.0,
    )

    should_be_in_graph = [
        task_artifact,
        task_artifact_with_key_not_latest,
        task_artifact_latest_in_collection,
        task_link_artifact,
        task_table_artifact_from_same_task,
        task_table_artifact,
        progress_type_artifact,
    ]

    should_not_be_in_graph = [
        result_type_artifact,
        latest_in_key_collection_but_not_this_flow_run,
    ]

    session.add_all(should_be_in_graph + should_not_be_in_graph)
    await session.commit()

    return should_be_in_graph


async def test_reading_graph_for_flow_run_with_artifacts(
    session: AsyncSession,
    flow_run,  # db.FlowRun
    flow_run_artifacts,  # List[db.Artifact],
    flow_run_task_artifacts,  # List[db.Artifact],
):
    expected_top_level_artifact, *_ = flow_run_artifacts

    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert graph.artifacts == [
        GraphArtifact(
            id=expected_top_level_artifact.id,
            created=expected_top_level_artifact.created,
            key=expected_top_level_artifact.key,
            type=expected_top_level_artifact.type,
            data=expected_top_level_artifact.data
            if expected_top_level_artifact.type == "progress"
            else None,
            is_latest=True,
        )
    ], (
        "Expected artifacts associated with the flow run but not with a task to be included at the roof of the graph."
    )

    expected_graph_artifacts = defaultdict(list)
    for task_artifact in flow_run_task_artifacts:
        expected_graph_artifacts[task_artifact.task_run_id].append(
            GraphArtifact(
                id=task_artifact.id,
                created=task_artifact.created,
                key=task_artifact.key,
                type=task_artifact.type,
                data=task_artifact.data if task_artifact.type == "progress" else None,
                is_latest=task_artifact.key is None
                or task_artifact.key == "collection-key--latest",
            )
        )

        # ensure that the artifacts are sorted by created time
        expected_graph_artifacts[task_artifact.task_run_id].sort(
            key=attrgetter("created")
        )

    graph_node_artifacts = {
        node.id: node.artifacts for _, node in graph.nodes if node.artifacts
    }

    assert expected_graph_artifacts == graph_node_artifacts


async def test_artifacts_on_flow_run_graph_limited_by_setting(
    session: AsyncSession,
    flow_run,  # db.FlowRun
    flow_run_artifacts,  # List[db.Artifact],
    flow_run_task_artifacts,  # List[db.Artifact],
):
    test_max_artifacts_setting = 2
    assert len(flow_run_task_artifacts) > test_max_artifacts_setting, (
        "Setup error - expected total # of graph artifacts to be greater than the limit being used for testing"
    )

    with temporary_settings(
        {PREFECT_API_MAX_FLOW_RUN_GRAPH_ARTIFACTS: test_max_artifacts_setting}
    ):
        graph = await read_flow_run_graph(
            session=session,
            flow_run_id=flow_run.id,
        )

    assert (
        len(graph.artifacts) + sum(len(node.artifacts) for _, node in graph.nodes)
    ) <= test_max_artifacts_setting


@pytest.fixture
async def flow_run_states(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
):
    states = [
        db.FlowRunState(
            flow_run_id=flow_run.id,
            type=StateType.RUNNING,
            name="Running",
            timestamp=now("UTC") - datetime.timedelta(minutes=1),
        ),
        db.FlowRunState(
            flow_run_id=flow_run.id,
            type=StateType.COMPLETED,
            name="Completed",
            timestamp=now("UTC"),
        ),
        db.FlowRunState(
            flow_run_id=flow_run.id,
            type=StateType.SCHEDULED,
            name="Scheduled",
            timestamp=now("UTC") - datetime.timedelta(minutes=3),
        ),
        db.FlowRunState(
            flow_run_id=flow_run.id,
            type=StateType.PENDING,
            name="Pending",
            timestamp=now("UTC") - datetime.timedelta(seconds=2),
        ),
    ]
    session.add_all(states)
    await session.commit()
    return states


async def test_reading_graph_for_flow_run_includes_states(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    flow_run_states,  # List[db.FlowRunState],
):
    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    expected_graph_states = sorted(
        (
            GraphState(
                id=state.id, timestamp=state.timestamp, type=state.type, name=state.name
            )
            for state in flow_run_states
        ),
        key=attrgetter("timestamp"),
    )

    assert graph.states == expected_graph_states


@pytest.fixture
def graph() -> Graph:
    return Graph(
        start_time=DateTime(1978, 6, 4, tzinfo=ZoneInfo("UTC")),
        end_time=DateTime(2023, 6, 4, tzinfo=ZoneInfo("UTC")),
        root_node_ids=[],
        nodes=[],
        artifacts=[],
        states=[],
    )


@pytest.fixture
def model_method_mock(graph: Graph, monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock()
    mock.return_value = graph
    monkeypatch.setattr("prefect.server.api.flow_runs.read_flow_run_graph", mock)
    return mock


async def test_missing_flow_run_returns_404(
    client: AsyncClient,
    model_method_mock: AsyncMock,
):
    flow_run_id = uuid4()

    model_method_mock.side_effect = ObjectNotFoundError

    response = await client.get(f"/flow_runs/{flow_run_id}/graph-v2")
    assert response.status_code == 404, response.text

    model_method_mock.assert_awaited_once_with(
        session=mock.ANY, flow_run_id=flow_run_id, since=earliest_possible_datetime()
    )


async def test_api_full(
    client: AsyncClient,
    model_method_mock: AsyncMock,
    graph: Graph,
):
    flow_run_id = uuid4()

    response = await client.get(f"/flow_runs/{flow_run_id}/graph-v2")
    assert response.status_code == 200, response.text

    model_method_mock.assert_awaited_once_with(
        session=mock.ANY, flow_run_id=flow_run_id, since=earliest_possible_datetime()
    )
    assert response.json() == graph.model_dump(mode="json")


async def test_simple_call(client: AsyncClient, flow_run: orm_models.FlowRun):
    """
    Regression test for https://github.com/PrefectHQ/prefect/issues/17729. Doesn't
    use a mock to ensure we go all the way to the database to verify the default
    since value works.
    """
    response = await client.get(f"/flow_runs/{flow_run.id}/graph-v2")
    assert response.status_code == 200, response.text
    assert response.json() is not None


async def test_api_incremental(
    client: AsyncClient,
    model_method_mock: AsyncMock,
    graph: Graph,
):
    flow_run_id = uuid4()

    response = await client.get(
        f"/flow_runs/{flow_run_id}/graph-v2",
        params={
            "since": "2023-06-04T01:02:03Z",
        },
    )
    assert response.status_code == 200, response.text

    model_method_mock.assert_awaited_once_with(
        session=mock.ANY,
        flow_run_id=flow_run_id,
        since=DateTime(2023, 6, 4, 1, 2, 3, tzinfo=ZoneInfo("UTC")),
    )
    assert response.json() == graph.model_dump(mode="json")


async def test_reading_graph_for_flow_run_with_linked_tasks_too_many_nodes(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: DateTime,
):
    with temporary_settings(
        updates={PREFECT_API_MAX_FLOW_RUN_GRAPH_NODES: 4},
    ):
        with pytest.raises(FlowRunGraphTooLarge) as exc_info:
            await read_flow_run_graph(
                session=session,
                flow_run_id=flow_run.id,
            )

    assert "has more than 4 nodes" in str(exc_info.value)


async def test_api_response_with_too_many_nodes(
    client: AsyncClient,
    model_method_mock: AsyncMock,
):
    model_method_mock.side_effect = FlowRunGraphTooLarge("too much, bro")

    response = await client.get(f"/flow_runs/{uuid4()}/graph-v2")
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "too much, bro"


@pytest.fixture
async def tasks_with_flow_run_inputs(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: DateTime,
) -> tuple:  # tuple[db.TaskRun, db.FlowRun, db.TaskRun]
    """Create a flow with task -> subflow -> task dependencies where downstream task directly references the subflow."""
    # Create upstream task
    upstream_task = db.TaskRun(
        id=uuid4(),
        flow_run_id=flow_run.id,
        name="upstream_task",
        task_key="upstream_task",
        dynamic_key="upstream_task",
        state_type=StateType.COMPLETED,
        state_name="Completed",
        expected_start_time=base_time
        + datetime.timedelta(seconds=1)
        - datetime.timedelta(microseconds=1),
        start_time=base_time + datetime.timedelta(seconds=1),
        end_time=base_time + datetime.timedelta(seconds=2),
    )
    session.add(upstream_task)

    # Create subflow wrapper task that depends on upstream task
    subflow_wrapper_task = db.TaskRun(
        id=uuid4(),
        flow_run_id=flow_run.id,
        name="subflow_wrapper",
        task_key="subflow_wrapper",
        dynamic_key="subflow_wrapper",
        state_type=StateType.COMPLETED,
        state_name="Completed",
        expected_start_time=base_time
        + datetime.timedelta(seconds=3)
        - datetime.timedelta(microseconds=1),
        start_time=base_time + datetime.timedelta(seconds=3),
        end_time=base_time + datetime.timedelta(seconds=10),
        task_inputs={"param": [{"id": upstream_task.id, "input_type": "task_run"}]},
    )
    session.add(subflow_wrapper_task)
    await session.flush()

    # Create subflow run
    subflow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow_run.flow_id,
        state_type=StateType.COMPLETED,
        state_name="Completed",
        expected_start_time=base_time
        + datetime.timedelta(seconds=4)
        - datetime.timedelta(microseconds=1),
        start_time=base_time + datetime.timedelta(seconds=4),
        end_time=base_time + datetime.timedelta(seconds=9),
        parent_task_run_id=subflow_wrapper_task.id,
    )
    session.add(subflow_run)

    # Create downstream task that directly references the subflow run
    downstream_task = db.TaskRun(
        id=uuid4(),
        flow_run_id=flow_run.id,
        name="downstream_task",
        task_key="downstream_task",
        dynamic_key="downstream_task",
        state_type=StateType.COMPLETED,
        state_name="Completed",
        expected_start_time=base_time
        + datetime.timedelta(seconds=11)
        - datetime.timedelta(microseconds=1),
        start_time=base_time + datetime.timedelta(seconds=11),
        end_time=base_time + datetime.timedelta(seconds=12),
        task_inputs={"param": [{"id": subflow_run.id, "input_type": "flow_run"}]},
    )
    session.add(downstream_task)

    await session.commit()

    return (upstream_task, subflow_run, downstream_task)


async def test_task_with_flow_run_input_creates_direct_edge(
    session: AsyncSession,
    flow,  # db.Flow,
    flow_run,  # db.FlowRun,
    tasks_with_flow_run_inputs: tuple,  # tuple[db.TaskRun, db.FlowRun, db.TaskRun]
):
    """Test that tasks with flow_run inputs create direct edges to the flow run."""
    upstream_task, subflow_run, downstream_task = tasks_with_flow_run_inputs

    graph = await read_flow_run_graph(
        session=session,
        flow_run_id=flow_run.id,
    )

    assert_graph_is_connected(graph)

    # Find nodes in the graph
    nodes_by_id = {node.id: node for _, node in graph.nodes}

    # Verify upstream task exists and has the subflow as a child
    assert upstream_task.id in nodes_by_id
    upstream_node = nodes_by_id[upstream_task.id]
    assert subflow_run.id in [child.id for child in upstream_node.children]

    # Verify subflow exists and has correct parents and children
    assert subflow_run.id in nodes_by_id
    subflow_node = nodes_by_id[subflow_run.id]
    assert upstream_task.id in [parent.id for parent in subflow_node.parents]
    assert downstream_task.id in [child.id for child in subflow_node.children]

    # Verify downstream task exists and has the subflow as a direct parent
    assert downstream_task.id in nodes_by_id
    downstream_node = nodes_by_id[downstream_task.id]
    assert subflow_run.id in [parent.id for parent in downstream_node.parents]

    # Ensure the graph shows the direct connection: upstream_task -> subflow_run -> downstream_task
    assert len(downstream_node.parents) == 1
    assert downstream_node.parents[0].id == subflow_run.id
