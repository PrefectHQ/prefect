from uuid import uuid4

import pytest

from prefect.client.orchestration import get_client
from prefect.client.schemas import filters
from prefect.server import models, schemas
from prefect.server.schemas import actions


class TestReadFlowRuns:
    @pytest.fixture
    async def flow_runs(self, flow, work_queue_1, session):
        flow_2 = await models.flows.create_flow(
            session=session,
            flow=actions.FlowCreate(name="another-test"),
        )

        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=actions.FlowRunCreate(flow_id=flow.id, name="fr1", tags=["red"]),
        )
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=actions.FlowRunCreate(flow_id=flow.id, name="fr2", tags=["blue"]),
        )
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow_2.id,
                name="fr3",
                tags=["blue", "red"],
                work_queue_id=work_queue_1.id,
            ),
        )
        await session.commit()
        return [flow_run_1, flow_run_2, flow_run_3]

    @pytest.fixture
    async def parent_flow_run(self, flow, session):
        flow_run = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                flow_id=flow.id,
                flow_version="1.0",
                state=schemas.states.Pending(),
            ),
        )
        await session.commit()
        return flow_run

    @pytest.fixture
    async def child_runs(
        self,
        flow,
        parent_flow_run,
        session,
    ):
        children = []
        for i in range(5):
            dummy_task = await models.task_runs.create_task_run(
                session=session,
                task_run=schemas.core.TaskRun(
                    flow_run_id=parent_flow_run.id,
                    name=f"dummy-{i}",
                    task_key=f"dummy-{i}",
                    dynamic_key=f"dummy-{i}",
                ),
            )
            children.append(
                await models.flow_runs.create_flow_run(
                    session=session,
                    flow_run=schemas.core.FlowRun(
                        flow_id=flow.id,
                        flow_version="1.0",
                        state=schemas.states.Pending(),
                        parent_task_run_id=dummy_task.id,
                    ),
                )
            )
        return children

    @pytest.fixture
    async def grandchild_runs(self, flow, child_runs, session):
        grandchildren = []
        for child in child_runs:
            for i in range(3):
                dummy_task = await models.task_runs.create_task_run(
                    session=session,
                    task_run=schemas.core.TaskRun(
                        flow_run_id=child.id,
                        name=f"dummy-{i}",
                        task_key=f"dummy-{i}",
                        dynamic_key=f"dummy-{i}",
                    ),
                )
                grandchildren.append(
                    await models.flow_runs.create_flow_run(
                        session=session,
                        flow_run=schemas.core.FlowRun(
                            flow_id=flow.id,
                            flow_version="1.0",
                            state=schemas.states.Pending(),
                            parent_task_run_id=dummy_task.id,
                        ),
                    )
                )
        return grandchildren

    async def test_read_subflow_runs(
        self,
        prefect_client,
        parent_flow_run,
        child_runs,
        # included to make sure we're only going 1 level deep
        grandchild_runs,
        # included to make sure we're not bringing in extra flow runs
        flow_runs,
    ):
        """We should be able to find all subflow runs of a given flow run."""
        subflow_filter = filters.FlowRunFilter(
            parent_flow_run_id=filters.FlowRunFilterParentFlowRunId(
                any_=[parent_flow_run.id]
            )
        )
        response = await prefect_client.read_flow_runs(flow_run_filter=subflow_filter)

        assert len(response) == len(child_runs)

        returned = {run.id for run in response}
        expected = {run.id for run in child_runs}
        assert returned == expected

    async def test_read_subflow_runs_non_existant(
        self,
        prefect_client,
    ):
        """With a UUID that isn't of a flow run, an empty list should be returned."""
        subflow_filter = filters.FlowRunFilter(
            parent_flow_run_id=filters.FlowRunFilterParentFlowRunId(any_=[uuid4()])
        )
        response = await prefect_client.read_flow_runs(flow_run_filter=subflow_filter)

        assert len(response) == 0


class TestCountFlowRuns:
    """Test the count_flow_runs client method with various filter combinations."""

    @pytest.fixture
    async def flow_runs(self, flow, session):
        flow_2 = await models.flows.create_flow(
            session=session,
            flow=actions.FlowCreate(name="flow-2", tags=["db"]),
        )

        flow_runs = []

        # Flow 1 runs
        flow_runs.append(
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    name="flow-1-1",
                    tags=["db", "blue"],
                    state=schemas.states.Completed(),
                ),
            )
        )
        flow_runs.append(
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    name="flow-1-2",
                    tags=["db", "red"],
                    state=schemas.states.Failed(),
                ),
            )
        )
        flow_runs.append(
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow.id,
                    name="flow-1-3",
                    tags=["blue"],
                    state=schemas.states.Running(),
                ),
            )
        )

        # Flow 2 runs
        flow_runs.append(
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow_2.id,
                    name="flow-2-1",
                    tags=["db"],
                    state=schemas.states.Completed(),
                ),
            )
        )
        flow_runs.append(
            await models.flow_runs.create_flow_run(
                session=session,
                flow_run=schemas.core.FlowRun(
                    flow_id=flow_2.id,
                    name="flow-2-2",
                    state=schemas.states.Scheduled(),
                ),
            )
        )

        await session.commit()
        return flow_runs

    # Test parameters: [filter_kwargs, expected_count]
    count_test_params = [
        # No filters - should return all flow runs
        ({}, 5),
        # Flow filters
        ({"flow_filter": filters.FlowFilter(name={"any_": ["flow-2"]})}, 2),
        ({"flow_filter": filters.FlowFilter(tags={"all_": ["db"]})}, 2),
        # Flow run filters
        ({"flow_run_filter": filters.FlowRunFilter(name={"like_": "flow-2"})}, 2),
        ({"flow_run_filter": filters.FlowRunFilter(tags={"all_": ["db", "red"]})}, 1),
        ({"flow_run_filter": filters.FlowRunFilter(tags={"is_null_": True})}, 1),
        # State filters
        (
            {
                "flow_run_filter": filters.FlowRunFilter(
                    state={"type": {"any_": ["COMPLETED"]}}
                )
            },
            2,
        ),
        (
            {
                "flow_run_filter": filters.FlowRunFilter(
                    state={"type": {"any_": ["FAILED"]}}
                )
            },
            1,
        ),
        # Combined filters
        (
            {
                "flow_filter": filters.FlowFilter(tags={"all_": ["db"]}),
                "flow_run_filter": filters.FlowRunFilter(tags={"all_": ["db"]}),
            },
            1,
        ),
        (
            {
                "flow_filter": filters.FlowFilter(name={"like_": "my-flow"}),
                "flow_run_filter": filters.FlowRunFilter(
                    state={"type": {"any_": ["COMPLETED"]}}
                ),
            },
            1,
        ),
        # Filters that should return nothing
        ({"flow_filter": filters.FlowFilter(name={"any_": ["nonexistent-flow"]})}, 0),
    ]

    @pytest.mark.parametrize("filter_kwargs,expected_count", count_test_params)
    async def test_async_count_flow_runs(
        self, flow_runs, filter_kwargs, expected_count
    ):
        async with get_client() as client:
            count = await client.count_flow_runs(**filter_kwargs)
            assert count == expected_count

    @pytest.mark.parametrize("filter_kwargs,expected_count", count_test_params)
    def test_sync_count_flow_runs(self, flow_runs, filter_kwargs, expected_count):
        with get_client(sync_client=True) as client:
            count = client.count_flow_runs(**filter_kwargs)
            assert count == expected_count
