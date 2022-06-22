from uuid import uuid4

import pendulum
import pytest
from sqlalchemy.exc import IntegrityError

from prefect.orion import models, schemas
from prefect.orion.exceptions import ObjectNotFoundError


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.core.WorkQueue(
            name="My WorkQueue",
            description="All about my work queue",
        ),
    )
    await session.commit()
    return work_queue


class TestCreateWorkQueue:
    async def test_create_work_queue_succeeds(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(name="My WorkQueue"),
        )
        assert work_queue.name == "My WorkQueue"

    async def test_create_work_queue_throws_exception_on_name_conflict(
        self,
        session,
        work_queue,
    ):
        with pytest.raises(IntegrityError):
            await models.work_queues.create_work_queue(
                session=session,
                work_queue=schemas.core.WorkQueue(
                    name=work_queue.name,
                ),
            )

    async def test_create_work_queue_throws_exception_on_name_conflict(
        self,
        session,
        work_queue,
    ):
        with pytest.raises(IntegrityError):
            await models.work_queues.create_work_queue(
                session=session,
                work_queue=schemas.core.WorkQueue(
                    name=work_queue.name,
                ),
            )


class TestReadWorkQueue:
    async def test_read_work_queue_by_id(self, session, work_queue):

        read_work_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert read_work_queue.name == work_queue.name

    async def test_read_work_queue_by_id_returns_none_if_does_not_exist(self, session):
        assert not await models.work_queues.read_work_queue(
            session=session, work_queue_id=uuid4()
        )


class TestReadWorkQueueByName:
    async def test_read_work_queue_by_name(self, session, work_queue):

        read_work_queue = await models.work_queues.read_work_queue_by_name(
            session=session, name=work_queue.name
        )
        assert read_work_queue.id == work_queue.id

    async def test_read_work_queue_by_name_returns_none_if_does_not_exist(
        self, session
    ):
        assert not await models.work_queues.read_work_queue_by_name(
            session=session, name="a name that doesn't exist"
        )


class TestReadWorkQueues:
    @pytest.fixture
    async def work_queues(self, session):

        work_queue_1 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue 1",
            ),
        )
        work_queue_2 = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="My WorkQueue 2",
            ),
        )
        await session.commit()
        return [work_queue_1, work_queue_2]

    async def test_read_work_queue(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(session=session)
        assert len(read_work_queue) == len(work_queues)

    async def test_read_work_queue_applies_limit(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session, limit=1
        )
        assert {queue.id for queue in read_work_queue} == {work_queues[0].id}

    async def test_read_work_queue_applies_offset(self, work_queues, session):
        read_work_queue = await models.work_queues.read_work_queues(
            session=session, offset=1
        )
        assert {queue.id for queue in read_work_queue} == {work_queues[1].id}

    async def test_read_work_queue_returns_empty_list(self, session):
        read_work_queue = await models.work_queues.read_work_queues(session=session)
        assert len(read_work_queue) == 0


class TestUpdateWorkQueue:
    async def test_update_work_queue(self, session, work_queue):
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                name="My Paused Queue",
                is_paused=True,
            ),
        )
        assert result

        updated_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert updated_queue.id == work_queue.id
        # relevant attributes should be updated
        assert updated_queue.name == "My Paused Queue"
        assert updated_queue.is_paused
        # unset attributes should be ignored
        assert updated_queue.description == work_queue.description

    async def test_update_work_queue_without_name(self, session, work_queue):
        assert work_queue.is_paused is False
        assert work_queue.concurrency_limit is None

        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=work_queue.id,
            work_queue=schemas.actions.WorkQueueUpdate(
                concurrency_limit=3,
                is_paused=True,
            ),
        )
        assert result

        updated_queue = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        # relevant attributes should be updated
        assert updated_queue.is_paused
        assert updated_queue.concurrency_limit == 3
        # unset attributes should be ignored
        assert updated_queue.description == work_queue.description
        assert updated_queue.id == work_queue.id
        assert updated_queue.name == work_queue.name

    async def test_update_work_queue_raises_on_bad_input_data(self, session):
        with pytest.raises(ValueError):
            await models.work_queues.update_work_queue(
                session=session,
                work_queue_id=str(uuid4()),
                work_queue=schemas.core.WorkQueue(name="naughty update data"),
            )

    async def test_update_work_queue_returns_false_if_does_not_exist(self, session):
        result = await models.work_queues.update_work_queue(
            session=session,
            work_queue_id=str(uuid4()),
            work_queue=schemas.actions.WorkQueueUpdate(),
        )
        assert result is False


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
    async def paused_work_queue(self, session):
        work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name="Paused",
                is_paused=True,
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
                flow_runner=schemas.core.FlowRunnerSettings(
                    type="test", config={"foo": "bar"}
                ),
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

    async def test_paused_work_queue_returns_empty_list(
        self, session, paused_work_queue
    ):
        assert (
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=paused_work_queue.id,
                scheduled_before=pendulum.now("UTC"),
            )
        ) == []

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

    async def test_get_runs_in_work_queue_filters_on_flow_runner_type(
        self,
        session,
        flow_run_1_id,
    ):
        # should only return SCHEDULED runs before NOW with
        # the correct flow_runner_type
        test_flow_runner_work_queue = await models.work_queues.create_work_queue(
            session=session,
            work_queue=schemas.core.WorkQueue(
                name=f"Work Queue for my very cool flow runner type",
                filter=schemas.core.QueueFilter(flow_runner_types=["test"]),
            ),
        )
        runs = await models.work_queues.get_runs_in_work_queue(
            session=session,
            work_queue_id=test_flow_runner_work_queue.id,
            scheduled_before=pendulum.now("UTC"),
        )
        assert {run.id for run in runs} == {flow_run_1_id}

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

    async def test_get_runs_in_work_queue_raises_object_not_found_error(self, session):
        with pytest.raises(ObjectNotFoundError):
            await models.work_queues.get_runs_in_work_queue(
                session=session,
                work_queue_id=uuid4(),
                scheduled_before=pendulum.now("UTC"),
            )


class TestDeleteWorkQueue:
    async def test_delete_work_queue(self, session, work_queue):
        assert await models.work_queues.delete_work_queue(
            session=session, work_queue_id=work_queue.id
        )

        # make sure the work_queue is deleted
        result = await models.work_queues.read_work_queue(
            session=session, work_queue_id=work_queue.id
        )
        assert result is None

    async def test_delete_work_queue_returns_false_if_does_not_exist(self, session):
        result = await models.work_queues.delete_work_queue(
            session=session, work_queue_id=str(uuid4())
        )
        assert result is False
