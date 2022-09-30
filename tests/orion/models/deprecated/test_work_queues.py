"""Tests deprecated tag-based matching systems for work queues"""
from uuid import uuid4

import pendulum
import pytest

from prefect.orion import models, schemas
from prefect.orion.exceptions import ObjectNotFoundError
from prefect.orion.models.deployments import check_work_queues_for_deployment


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.core.WorkQueue(
            name="My WorkQueue",
            description="All about my work queue",
            # filters for all runs
            filter=schemas.core.QueueFilter(),
        ),
    )
    await session.commit()
    return work_queue


class TestCreateWorkQueue:
    async def test_create_work_queue_succeeds(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue", filter=schemas.core.QueueFilter()
            ),
        )
        assert work_queue.name == "My WorkQueue"
        assert work_queue.filter is not None


class TestUpdateWorkQueue:
    async def test_update_work_queue(self, session, work_queue):
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                filter=schemas.core.QueueFilter(tags=["updated", "tags"])
            ),
        )
        assert result

        updated_queue = schemas.core.WorkQueue.from_orm(
            await models.work_queues.read_work_queue(
                session=session, work_queue_id=work_queue.id
            )
        )
        assert updated_queue.id == work_queue.id
        assert updated_queue.filter.tags == ["updated", "tags"]


class TestGetRunsInWorkQueue:
    @pytest.fixture
    async def tb12_work_queue(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="TB12",
                description="The GOAT",
                filter=schemas.core.QueueFilter(tags=["tb12"]),
            ),
        )
        await session.commit()
        return work_queue

    @pytest.fixture
    async def flow_run_1_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_2_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_3_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_4_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_5_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_6_id(self):
        return uuid4()

    @pytest.fixture
    async def flow_run_7_id(self):
        return uuid4()

    @pytest.fixture(autouse=True)
    async def flow_runs(
        self,
        session,
        deployment,
        infrastructure_document_id,
        flow_run_1_id,
        flow_run_2_id,
        flow_run_3_id,
        flow_run_4_id,
        flow_run_5_id,
        flow_run_6_id,
        flow_run_7_id,
    ):

        # flow run 1 is in a SCHEDULED state 5 seconds ago
        flow_run_1 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_1_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
                infrastructure_document_id=infrastructure_document_id,
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_1.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(seconds=1)
                ),
            ),
        )

        # flow run 2 is in a SCHEDULED state 1 minute ago with tags ["tb12", "goat"]
        flow_run_2 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_2_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
                tags=["tb12", "goat"],
                next_scheduled_start_time=pendulum.now("UTC").subtract(minutes=1),
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_2.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(minutes=1),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(minutes=1)
                ),
            ),
        )

        # flow run 3 is in a PENDING state with tags ["tb12", "goat"]
        flow_run_3 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_3_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
                tags=["tb12", "goat"],
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_3.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(seconds=1)
                ),
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_3.id,
            state=schemas.states.Pending(),
        )

        # flow run 4 is in a RUNNING state with no tags
        flow_run_4 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_4_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_4.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(seconds=1)
                ),
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_4.id,
            state=schemas.states.Pending(),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_4.id,
            state=schemas.states.Running(),
        )

        # flow run 5 is in a SCHEDULED state 1 year in the future
        flow_run_5 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_5_id,
                flow_id=deployment.flow_id,
                deployment_id=deployment.id,
                flow_version="0.1",
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_5.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(scheduled_time=pendulum.now("UTC").add(years=1)),
            ),
        )

        # flow run 6 is in a SCHEDULED state 5 seconds ago but has no
        # deployment_id, it should never be returned by the queue
        flow_run_6 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_6_id,
                flow_id=deployment.flow_id,
                flow_version="0.1",
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_6.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(seconds=1)
                ),
            ),
        )

        # flow run 7 is in a RUNNING state but has no
        # deployment_id, it should never be returned by the queue
        # or count against concurrency limits
        flow_run_7 = await models.flow_runs.create_flow_run(
            session=session,
            flow_run=schemas.core.FlowRun(
                id=flow_run_7_id,
                flow_id=deployment.flow_id,
                flow_version="0.1",
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_7.id,
            state=schemas.states.State(
                type=schemas.states.StateType.SCHEDULED,
                timestamp=pendulum.now("UTC").subtract(seconds=5),
                state_details=dict(
                    scheduled_time=pendulum.now("UTC").subtract(seconds=1)
                ),
            ),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_7.id,
            state=schemas.states.Pending(),
        )
        await models.flow_runs.set_flow_run_state(
            session=session,
            flow_run_id=flow_run_7.id,
            state=schemas.states.Running(),
        )
        await session.commit()

    async def test_get_runs_in_work_queue_returns_scheduled_runs(
        self,
        session,
        work_queue,
        flow_run_1_id,
        flow_run_2_id,
    ):
        # should only return SCHEDULED runs before NOW with
        # a deployment_id
        runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        )
        assert {run.id for run in runs} == {flow_run_1_id, flow_run_2_id}

        # should respect limit param
        limited_runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=pendulum.now("UTC"),
            limit=1,
        )
        # flow run 2 is scheduled to start before flow run 1
        assert {run.id for run in limited_runs} == {flow_run_2_id}

        # should respect scheduled before param
        # (turns out pendulum does not actually let you go back far enough but you get the idea)
        runs_from_babylon = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=pendulum.now("UTC").subtract(years=2000),
            limit=1,
        )
        assert len(runs_from_babylon) == 0

    async def test_get_runs_in_work_queue_filters_on_tags(
        self,
        session,
        tb12_work_queue,
        flow_run_2_id,
    ):
        # should only return SCHEDULED runs before NOW with
        # a deployment_id and tags ["tb12"]
        runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=tb12_work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        )
        assert {run.id for run in runs} == {flow_run_2_id}

    async def test_get_runs_in_work_queue_filters_on_deployment_ids(
        self,
        session,
        deployment,
        flow_run_1_id,
        flow_run_2_id,
    ):
        # should only return SCHEDULED runs before NOW with
        # the correct deployment_id
        deployment_work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name=f"Work Queue for Deployment {deployment.name}",
                filter=schemas.core.QueueFilter(
                    deployment_ids=[deployment.id, uuid4()]
                ),
            ),
        )
        runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=deployment_work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        )
        assert {run.id for run in runs} == {flow_run_1_id, flow_run_2_id}

        bad_deployment_work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name=f"Work Queue for Deployment that doesnt exist",
                filter=schemas.core.QueueFilter(deployment_ids=[uuid4()]),
            ),
        )
        assert (
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=bad_deployment_work_queue.id,
                scheduled_before=pendulum.now("UTC"),
            )
        ) == []

    async def test_get_runs_in_work_queue_uses_union_of_filter_criteria(self, session):
        # tags "tb12" will match but the deployment ids should not match any flow runs
        conflicting_filter_work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name=f"Work Queue for Deployment that doesnt exist",
                filter=schemas.core.QueueFilter(
                    deployment_ids=[uuid4()], tags=["tb12"]
                ),
            ),
        )
        assert (
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=conflicting_filter_work_queue.id,
                scheduled_before=pendulum.now("UTC"),
            )
        ) == []

    async def test_get_runs_in_work_queue_respects_concurrency_limit(
        self,
        session,
        work_queue,
        flow_run_1_id,
        flow_run_2_id,
    ):
        runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        )
        assert {run.id for run in runs} == {flow_run_1_id, flow_run_2_id}

        # add a concurrency limit
        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(concurrency_limit=2),
        )
        # since there is one PENDING and one RUNNING flow run, no runs
        # should be returned
        assert (
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=work_queue.id,
                scheduled_before=pendulum.now("UTC"),
            )
        ) == []

        # since there is one PENDING and one RUNNING flow run, no runs
        # should be returned, even if a larger limit has been provided
        assert (
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=work_queue.id,
                scheduled_before=pendulum.now("UTC"),
                limit=9001,
            )
        ) == []

        # increase the concurrency limit
        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(concurrency_limit=3),
        )
        # since there is one PENDING and one RUNNING flow run, one
        # flow run should be returned
        runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        )
        assert {run.id for run in runs} == {flow_run_2_id}

    async def test_get_runs_in_work_queue_respects_concurrency_limit_of_0(
        self,
        session,
        work_queue,
    ):
        # set concurrency limit to 0
        await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(concurrency_limit=0),
        )

        await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        ) == []

    async def test_get_runs_in_work_queue_raises_object_not_found_error(self, session):
        with pytest.raises(ObjectNotFoundError):
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=uuid4(),
                scheduled_before=pendulum.now("UTC"),
            )


class TestCheckWorkQueuesForDeployment:
    async def setup_work_queues_and_deployment(
        self, session, flow, flow_function, tags=[]
    ):
        """
        Create combinations of work queues, and a deployment to make sure that query is working correctly.

        Returns the ID of the deployment that was created and a random ID that was provided to work queues
        for testing purposes.
        """
        deployment = (
            await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    name="My Deployment",
                    manifest_path="file.json",
                    flow_id=flow.id,
                    tags=tags,
                ),
            ),
        )
        match_id = deployment[0].id
        miss_id = uuid4()

        tags = [  # "a" and "b" are matches and "y" and "z" are misses
            [],
            ["a"],
            ["z"],
            ["a", "b"],
            ["a", "z"],
            ["y", "z"],
        ]

        deployments = [
            [],
            [match_id],
            [miss_id],
            [match_id, miss_id],
        ]

        # Generate all combinations of work queues
        for t in tags:
            for d in deployments:

                await models.work_queues.create_work_queue(
                    session=session,
                    work_queue=schemas.core.WorkQueue(
                        name=f"{t}:{d}",
                        filter=schemas.core.QueueFilter(tags=t, deployment_ids=d),
                    ),
                )

        # return the two IDs needed to compare results
        return match_id, miss_id

    async def assert_queues_found(self, session, deployment_id, desired_queues):
        queues = await check_work_queues_for_deployment(
            session=session, deployment_id=deployment_id
        )
        actual_queue_attrs = [[q.filter.tags, q.filter.deployment_ids] for q in queues]

        for q in desired_queues:
            assert q in actual_queue_attrs

    async def test_object_not_found_error_raised(self, session):
        with pytest.raises(ObjectNotFoundError):
            await check_work_queues_for_deployment(
                session=session, deployment_id=uuid4()
            )

    # NO TAG DEPLOYMENTS with no-tag queues
    async def test_no_tag_picks_up_no_filter_q(self, session, flow, flow_function):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function
        )
        match_q = [[[], []]]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_no_tag_picks_up_no_tags_no_runners_with_id_match_q(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function
        )
        match_q = [
            [[], [match_id]],
            [[], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_no_tag_picks_up_no_tags_no_id_with_runners_match(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function
        )
        match_q = [
            [[], []],
            [[], []],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_no_tag_picks_up_no_tags_with_id_and_runners_match(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function
        )
        match_q = [
            [[], [match_id]],
            [[], [match_id, miss_id]],
            [[], [match_id]],
            [[], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_no_tag_picks_up_only_number_of_expected_queues(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function
        )

        actual_queues = await check_work_queues_for_deployment(
            session=session, deployment_id=match_id
        )

        assert len(actual_queues) == 3

    # ONE TAG DEPLOYMENTS with no-tag queues
    async def test_one_tag_picks_up_no_filter_q(self, session, flow, flow_function):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a"]
        )
        match_q = [[[], []]]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_one_tag_picks_up_no_tags_with_id_match_q(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a"]
        )
        match_q = [
            [[], [match_id]],
            [[], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    # ONE TAG DEPLOYMENTS with one-tag queues
    async def test_one_tag_picks_up_one_tag_q(self, session, flow, flow_function):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a"]
        )
        match_q = [[["a"], []]]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_one_tag_picks_up_one_tag_with_id_match_q(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a"]
        )
        match_q = [
            [["a"], [match_id]],
            [["a"], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_one_tag_picks_up_only_number_of_expected_queues(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a"]
        )

        actual_queues = await check_work_queues_for_deployment(
            session=session, deployment_id=match_id
        )

        assert len(actual_queues) == 6

    # TWO TAG DEPLOYMENTS with no-tag queues
    async def test_two_tag_picks_up_no_filter_q(self, session, flow, flow_function):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )
        match_q = [[[], []]]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_two_tag_picks_up_no_tags_with_id_match_q(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )
        match_q = [
            [[], [match_id]],
            [[], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    # TWO TAG DEPLOYMENTS with one-tag queues
    async def test_two_tag_picks_up_one_tag_q(self, session, flow, flow_function):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )
        match_q = [[["a"], []]]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_two_tag_picks_up_one_tag_with_id_match_q(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )
        match_q = [
            [["a"], [match_id]],
            [["a"], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    # TWO TAG DEPLOYMENTS with two-tag queues
    async def test_two_tag_picks_up_two_tag_q(self, session, flow, flow_function):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )
        match_q = [[["a", "b"], []]]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_two_tag_picks_up_two_tag_with_id_match_q(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )
        match_q = [
            [["a", "b"], [match_id]],
            [["a", "b"], [match_id, miss_id]],
        ]
        await self.assert_queues_found(session, match_id, match_q)

    async def test_two_tag_picks_up_only_number_of_expected_queues(
        self, session, flow, flow_function
    ):
        match_id, miss_id = await self.setup_work_queues_and_deployment(
            session=session, flow=flow, flow_function=flow_function, tags=["a", "b"]
        )

        actual_queues = await check_work_queues_for_deployment(
            session=session, deployment_id=match_id
        )

        assert len(actual_queues) == 9
