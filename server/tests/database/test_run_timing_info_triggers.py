# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Tests that when a state is inserted into the state table, it updates the
associated run's timing details via Postgres trigger
"""
import pendulum
import pytest

from prefect_server.database import models


@pytest.fixture(autouse=True)
async def reset_states(flow_run_id, task_run_id):
    await models.FlowRunState.where({"flow_run_id": {"_eq": flow_run_id}}).delete()
    await models.TaskRunState.where({"task_run_id": {"_eq": task_run_id}}).delete()
    await models.FlowRun.where({"id": {"_eq": flow_run_id}}).update(
        dict(start_time=None, end_time=None, duration=None)
    )
    await models.TaskRun.where({"id": {"_eq": task_run_id}}).update(
        dict(start_time=None, end_time=None, duration=None, run_count=0)
    )


class TestFlowRunStateTrigger:
    async def test_inserting_non_running_states_has_no_effect(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})
        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(**details, version=1, state="Scheduled"),
                models.FlowRunState(**details, version=2, state="Failed"),
                models.FlowRunState(**details, version=3, state="Retrying"),
                models.FlowRunState(**details, version=4, state="Retrying"),
            ]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time is None
        assert run.end_time is None
        assert run.duration is None

    async def test_inserting_running_state_has_effect(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})
        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(**details, version=1, state="Running"),
                models.FlowRunState(**details, version=2, state="Failed"),
                models.FlowRunState(**details, version=3, state="Retrying"),
                models.FlowRunState(**details, version=4, state="Retrying"),
            ]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time is not None
        assert run.end_time is not None
        assert run.duration is not None

    async def test_inserting_running_state_later_has_effect(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})
        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(**details, version=2, state="Failed"),
                models.FlowRunState(**details, version=3, state="Retrying"),
                models.FlowRunState(**details, version=4, state="Retrying"),
            ]
        )

        await models.FlowRunState.insert_many(
            [models.FlowRunState(**details, version=1, state="Running")]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time is not None
        assert run.end_time is not None
        assert run.duration is not None

    async def test_start_and_end_from_running_state(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)

        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.FlowRunState(**details, version=2, state="Failed", timestamp=et),
                models.FlowRunState(**details, version=3, state="Retrying"),
                models.FlowRunState(**details, version=4, state="Retrying"),
            ]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()

    async def test_no_end_if_running_is_last_state(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})

        st = pendulum.now("UTC")

        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
            ]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time == st
        assert run.end_time is None
        assert run.duration is None

    async def test_start_and_end_from_multiple_running_states(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)
        not_et = pendulum.now("UTC").add(hours=1)

        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.FlowRunState(**details, version=2, state="Failed"),
                models.FlowRunState(**details, version=3, state="Retrying"),
                models.FlowRunState(**details, version=4, state="Running"),
                models.FlowRunState(**details, version=5, state="Failed"),
                models.FlowRunState(**details, version=6, state="Retrying"),
                models.FlowRunState(**details, version=7, state="Running"),
                models.FlowRunState(
                    **details, version=8, state="Success", timestamp=et
                ),
                models.FlowRunState(
                    **details, version=9, state="Success", timestamp=not_et
                ),
            ]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()

    async def test_version_order_determines_timestamp(self, flow_run_id):
        details = dict(flow_run_id=flow_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)
        not_et = pendulum.now("UTC").add(hours=1)

        await models.FlowRunState.insert_many(
            [
                models.FlowRunState(**details, version=0, state="Pending"),
                models.FlowRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.FlowRunState(**details, version=2, state="Failed"),
                models.FlowRunState(**details, version=3, state="Retrying"),
                models.FlowRunState(**details, version=4, state="Running"),
                models.FlowRunState(**details, version=6, state="Failed"),
                models.FlowRunState(**details, version=7, state="Retrying"),
                models.FlowRunState(**details, version=8, state="Running"),
                models.FlowRunState(
                    **details, version=5, state="Success", timestamp=not_et
                ),
                models.FlowRunState(
                    **details, version=9, state="Success", timestamp=et
                ),
            ]
        )

        run = await models.FlowRun.where(id=flow_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()


class TestTaskRunStateTrigger:
    async def test_inserting_non_running_states_has_no_effect(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})
        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(**details, version=1, state="Scheduled"),
                models.TaskRunState(**details, version=2, state="Failed"),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Retrying"),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time is None
        assert run.end_time is None
        assert run.duration is None
        assert run.run_count == 0

    async def test_inserting_running_state_has_effect(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})
        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(**details, version=1, state="Running"),
                models.TaskRunState(**details, version=2, state="Failed"),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Retrying"),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time is not None
        assert run.end_time is not None
        assert run.duration is not None
        assert run.run_count == 1

    async def test_inserting_running_state_later_has_effect(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})
        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(**details, version=2, state="Failed"),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Retrying"),
            ]
        )

        await models.TaskRunState.insert_many(
            [models.TaskRunState(**details, version=1, state="Running")]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time is not None
        assert run.end_time is not None
        assert run.duration is not None
        assert run.run_count == 1

    async def test_start_and_end_from_running_state(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)

        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.TaskRunState(**details, version=2, state="Failed", timestamp=et),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Retrying"),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()
        assert run.run_count == 1

    async def test_no_end_if_running_is_last_state(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})

        st = pendulum.now("UTC")

        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration"}
        )
        assert run.start_time == st
        assert run.end_time is None
        assert run.duration is None

    async def test_start_and_end_from_multiple_running_states(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)
        not_et = pendulum.now("UTC").add(hours=1)

        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.TaskRunState(**details, version=2, state="Failed"),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Running"),
                models.TaskRunState(**details, version=5, state="Failed"),
                models.TaskRunState(**details, version=6, state="Retrying"),
                models.TaskRunState(**details, version=7, state="Running"),
                models.TaskRunState(
                    **details, version=8, state="Success", timestamp=et
                ),
                models.TaskRunState(
                    **details, version=9, state="Success", timestamp=not_et
                ),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()
        assert run.run_count == 3

    async def test_version_order_determines_timestamp(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)
        not_et = pendulum.now("UTC").add(hours=1)

        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.TaskRunState(**details, version=2, state="Failed"),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Running"),
                models.TaskRunState(**details, version=6, state="Failed"),
                models.TaskRunState(**details, version=7, state="Retrying"),
                models.TaskRunState(**details, version=8, state="Running"),
                models.TaskRunState(
                    **details, version=5, state="Success", timestamp=not_et
                ),
                models.TaskRunState(
                    **details, version=9, state="Success", timestamp=et
                ),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()
        assert run.run_count == 3

    async def test_looping_doesnt_inflate_run_count(self, task_run_id):
        details = dict(task_run_id=task_run_id, serialized_state={})

        st = pendulum.now("UTC")
        et = pendulum.now("UTC").add(days=1)
        not_et = pendulum.now("UTC").add(hours=1)

        await models.TaskRunState.insert_many(
            [
                models.TaskRunState(**details, version=0, state="Pending"),
                models.TaskRunState(
                    **details, version=1, state="Running", timestamp=st
                ),
                models.TaskRunState(**details, version=2, state="Failed"),
                models.TaskRunState(**details, version=3, state="Retrying"),
                models.TaskRunState(**details, version=4, state="Running"),
                models.TaskRunState(**details, version=5, state="Looped"),
                models.TaskRunState(**details, version=6, state="Running"),
                models.TaskRunState(**details, version=7, state="Looped"),
                models.TaskRunState(**details, version=8, state="Running"),
                models.TaskRunState(**details, version=9, state="Looped"),
                models.TaskRunState(**details, version=10, state="Running"),
                models.TaskRunState(
                    **details, version=11, state="Success", timestamp=et
                ),
            ]
        )

        run = await models.TaskRun.where(id=task_run_id).first(
            {"start_time", "end_time", "duration", "run_count"}
        )
        assert run.start_time == st
        assert run.end_time == et
        assert run.duration == (et - st).as_timedelta()
        assert run.run_count == 2
