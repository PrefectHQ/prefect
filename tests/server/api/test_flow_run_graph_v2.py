from datetime import datetime
from typing import Iterable, List, Union
from unittest import mock
from unittest.mock import AsyncMock
from uuid import uuid4

import pendulum
import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database.interface import PrefectDBInterface
from prefect.server.exceptions import FlowRunGraphTooLarge, ObjectNotFoundError
from prefect.server.models.flow_runs import read_flow_run_graph
from prefect.server.schemas.graph import Edge, Graph, Node
from prefect.server.schemas.states import StateType
from prefect.settings import PREFECT_API_MAX_FLOW_RUN_GRAPH_NODES, temporary_settings


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
        last_seen = pendulum.datetime(1978, 6, 4)
        for item in items:
            try:
                node = nodes_by_id[item.id]
            except KeyError:
                if incremental:
                    continue
                raise

            assert node.start_time >= last_seen
            last_seen = pendulum.instance(node.start_time)

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
def base_time(start_of_test: pendulum.DateTime) -> pendulum.DateTime:
    return start_of_test.subtract(minutes=5)


@pytest.fixture
async def unstarted_flow_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow,  # : db.Flow,
    base_time: pendulum.DateTime,
):
    flow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow.id,
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time.subtract(seconds=1),
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
    base_time: pendulum.DateTime,
):
    flow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow.id,
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time.subtract(seconds=1),
        start_time=base_time,
        end_time=base_time.add(minutes=5),
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


@pytest.fixture
async def flat_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: pendulum.DateTime,
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
            expected_start_time=base_time.add(seconds=i).subtract(microseconds=1),
            start_time=base_time.add(seconds=i),
            end_time=base_time.add(minutes=1, seconds=i),
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
            expected_start_time=base_time.add(seconds=3).subtract(microseconds=1),
            start_time=base_time.add(seconds=3),
            end_time=base_time.add(minutes=1, seconds=3),
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
            ),
        )
        for task_run in flat_tasks
    ]

    assert_graph_is_connected(graph)


@pytest.fixture
async def linked_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: pendulum.DateTime,
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
            expected_start_time=base_time.add(seconds=i).subtract(microseconds=1),
            start_time=base_time.add(seconds=i),
            end_time=base_time.add(minutes=1, seconds=i),
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
                expected_start_time=base_time.add(seconds=index + j).subtract(
                    microseconds=1
                ),
                start_time=base_time.add(seconds=index + j),
                end_time=base_time.add(minutes=1, seconds=index + j),
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
            expected_start_time=base_time.add(seconds=3).subtract(microseconds=1),
            start_time=base_time.add(seconds=3),
            end_time=base_time.add(minutes=1, seconds=3),
        )
    )

    await session.commit()
    return task_runs


async def test_reading_graph_for_flow_run_with_linked_tasks(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: pendulum.DateTime,
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
                start_time=base_time.add(seconds=0),
                end_time=base_time.add(minutes=1, seconds=0),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
            ),
        ),
        (
            linked_tasks[1].id,
            Node(
                kind="task-run",
                id=linked_tasks[1].id,
                label="task-1",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=1),
                end_time=base_time.add(minutes=1, seconds=1),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
            ),
        ),
        (
            linked_tasks[2].id,
            Node(
                kind="task-run",
                id=linked_tasks[2].id,
                label="task-2",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=2),
                end_time=base_time.add(minutes=1, seconds=2),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
            ),
        ),
        (
            linked_tasks[3].id,
            Node(
                kind="task-run",
                id=linked_tasks[3].id,
                label="task-3",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=3),
                end_time=base_time.add(minutes=1, seconds=3),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
            ),
        ),
        (
            linked_tasks[4].id,
            Node(
                kind="task-run",
                id=linked_tasks[4].id,
                label="task-4",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=4),
                end_time=base_time.add(minutes=1, seconds=4),
                parents=[
                    Edge(id=linked_tasks[0].id),
                    Edge(id=linked_tasks[1].id),
                ],
                children=[],
            ),
        ),
        (
            linked_tasks[5].id,
            Node(
                kind="task-run",
                id=linked_tasks[5].id,
                label="task-5",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=5),
                end_time=base_time.add(minutes=1, seconds=5),
                parents=[
                    Edge(id=linked_tasks[2].id),
                    Edge(id=linked_tasks[3].id),
                ],
                children=[],
            ),
        ),
    ]


async def test_reading_graph_for_flow_run_with_linked_unstarted_tasks(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: pendulum.DateTime,
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
                start_time=base_time.add(seconds=0).subtract(microseconds=1),
                end_time=base_time.add(minutes=1, seconds=0),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
            ),
        ),
        (
            linked_tasks[1].id,
            Node(
                kind="task-run",
                id=linked_tasks[1].id,
                label="task-1",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=1).subtract(microseconds=1),
                end_time=base_time.add(minutes=1, seconds=1),
                parents=[],
                children=[
                    Edge(id=linked_tasks[4].id),
                ],
            ),
        ),
        (
            linked_tasks[2].id,
            Node(
                kind="task-run",
                id=linked_tasks[2].id,
                label="task-2",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=2).subtract(microseconds=1),
                end_time=base_time.add(minutes=1, seconds=2),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
            ),
        ),
        (
            linked_tasks[3].id,
            Node(
                kind="task-run",
                id=linked_tasks[3].id,
                label="task-3",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=3).subtract(microseconds=1),
                end_time=base_time.add(minutes=1, seconds=3),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
            ),
        ),
        (
            linked_tasks[4].id,
            Node(
                kind="task-run",
                id=linked_tasks[4].id,
                label="task-4",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=4).subtract(microseconds=1),
                end_time=base_time.add(minutes=1, seconds=4),
                parents=[
                    Edge(id=linked_tasks[0].id),
                    Edge(id=linked_tasks[1].id),
                ],
                children=[],
            ),
        ),
        (
            linked_tasks[5].id,
            Node(
                kind="task-run",
                id=linked_tasks[5].id,
                label="task-5",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=5).subtract(microseconds=1),
                end_time=base_time.add(minutes=1, seconds=5),
                parents=[
                    Edge(id=linked_tasks[2].id),
                    Edge(id=linked_tasks[3].id),
                ],
                children=[],
            ),
        ),
    ]


async def test_reading_graph_for_flow_run_with_linked_tasks_incrementally(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: pendulum.DateTime,
):
    # `since` is just after the second task ends, so we should only get the last four
    since = base_time.add(minutes=1, seconds=1, microseconds=1000)
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
                start_time=base_time.add(seconds=2),
                end_time=base_time.add(minutes=1, seconds=2),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
            ),
        ),
        (
            linked_tasks[3].id,
            Node(
                kind="task-run",
                id=linked_tasks[3].id,
                label="task-3",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=3),
                end_time=base_time.add(minutes=1, seconds=3),
                parents=[],
                children=[
                    Edge(id=linked_tasks[5].id),
                ],
            ),
        ),
        (
            linked_tasks[4].id,
            Node(
                kind="task-run",
                id=linked_tasks[4].id,
                label="task-4",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=4),
                end_time=base_time.add(minutes=1, seconds=4),
                parents=[
                    # important: these are not present in the node list because they
                    # already ended but we still have the edges referencing them
                    Edge(id=linked_tasks[0].id),
                    Edge(id=linked_tasks[1].id),
                ],
                children=[],
            ),
        ),
        (
            linked_tasks[5].id,
            Node(
                kind="task-run",
                id=linked_tasks[5].id,
                label="task-5",
                state_type=StateType.COMPLETED,
                start_time=base_time.add(seconds=5),
                end_time=base_time.add(minutes=1, seconds=5),
                parents=[
                    Edge(id=linked_tasks[2].id),
                    Edge(id=linked_tasks[3].id),
                ],
                children=[],
            ),
        ),
    ]


@pytest.fixture
async def subflow_run(
    db: PrefectDBInterface,
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    base_time: pendulum.DateTime,
):
    wrapper_task = db.TaskRun(
        id=uuid4(),
        flow_run_id=flow_run.id,
        name="task-0",
        task_key="task-0",
        dynamic_key="task-0",
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time.subtract(microseconds=1),
        start_time=base_time.add(seconds=1),
        end_time=base_time.add(minutes=1),
    )
    session.add(wrapper_task)
    await session.flush()

    subflow_run = db.FlowRun(
        id=uuid4(),
        flow_id=flow_run.flow_id,
        state_type=StateType.COMPLETED,
        state_name="Irrelevant",
        expected_start_time=base_time.subtract(microseconds=1),
        start_time=base_time,
        end_time=base_time.add(minutes=5),
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
def graph() -> Graph:
    return Graph(
        start_time=pendulum.datetime(1978, 6, 4),
        end_time=pendulum.datetime(2023, 6, 4),
        root_node_ids=[],
        nodes=[],
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
        session=mock.ANY,
        flow_run_id=flow_run_id,
        since=datetime.min,
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
        session=mock.ANY,
        flow_run_id=flow_run_id,
        since=datetime.min,
    )
    assert response.json() == graph.dict(json_compatible=True)


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
        since=pendulum.datetime(2023, 6, 4, 1, 2, 3),
    )
    assert response.json() == graph.dict(json_compatible=True)


async def test_reading_graph_for_flow_run_with_linked_tasks_too_many_nodes(
    session: AsyncSession,
    flow_run,  # db.FlowRun,
    linked_tasks: List,  # List[db.TaskRun],
    base_time: pendulum.DateTime,
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
