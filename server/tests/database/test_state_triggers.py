# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Tests that when a state is inserted into the state table, it updates the
associated run's details via Postgres trigger
"""
import pendulum
import pytest

from prefect_server.database import models


class TestFlowRunStateTrigger:
    @pytest.mark.parametrize("original_version", [-1, 0, 9, 10])
    async def test_trigger_updates_run_when_state_version_is_greater_or_equal(
        self, flow_run_id, original_version
    ):

        await models.FlowRun.where(id=flow_run_id).update({"version": original_version})
        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        assert new_run.version == 10
        assert new_run.state_id != old_run.state_id
        assert new_run.heartbeat is None

    async def test_equal_version_only_updates_if_timestamp_is_greater_than_current(
        self, flow_run_id
    ):

        dt = pendulum.now("utc")
        await models.FlowRun.where(id=flow_run_id).update(
            {"version": 10, "state_timestamp": dt, "state_message": "a"}
        )

        # same version, earlier timestamp
        await models.FlowRunState(
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt.subtract(seconds=1),
            start_time=dt,
            message="b",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"state_message", "state_timestamp"}
        )

        assert new_run.state_message == "a"
        assert new_run.state_timestamp == dt

        # same version, later timestamp
        await models.FlowRunState(
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt.add(seconds=1),
            start_time=dt,
            message="c",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"state_message", "state_timestamp"}
        )

        assert new_run.state_message == "c"
        assert new_run.state_timestamp == dt.add(seconds=1)

    async def test_trigger_updates_highest_version_when_multiple_states_inserted(
        self, flow_run_id
    ):

        await models.FlowRun.where(id=flow_run_id).update({"version": 10})
        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        dt = pendulum.now("UTC")

        await models.FlowRunState().insert_many(
            [
                dict(
                    flow_run_id=flow_run_id,
                    version=v,
                    timestamp=dt.add(seconds=v),
                    start_time=dt.add(seconds=v),
                    message="x",
                    result="y",
                    state="z",
                    serialized_state={"a": "b"},
                )
                for v in [1, 5, 10, 11, 12, 100]
            ]
        )

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "state_timestamp", "state_id"}
        )

        assert new_run.version == 100 != old_run.version
        assert new_run.state_id != old_run.state_id
        assert new_run.state_timestamp == dt.add(seconds=100)

    @pytest.mark.parametrize("original_version", [11, 100])
    async def test_trigger_does_not_update_run_when_when_state_version_is_lower(
        self, flow_run_id, original_version
    ):

        await models.FlowRun.where(id=flow_run_id).update({"version": original_version})

        old_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        dt = pendulum.now("UTC")

        await models.FlowRunState(
            flow_run_id=flow_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.FlowRun.where(id=flow_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        assert new_run.version == old_run.version
        assert new_run.state_id == old_run.state_id
        assert new_run.heartbeat is None


class TestTaskRunStateTrigger:
    @pytest.mark.parametrize("original_version", [-1, 0, 9, 10])
    async def test_trigger_updates_run_when_state_version_is_greater_or_equal(
        self, task_run_id, original_version
    ):

        await models.TaskRun.where(id=task_run_id).update({"version": original_version})
        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            task_run_id=task_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        assert new_run.version == 10
        assert new_run.state_id != old_run.state_id
        assert new_run.heartbeat is None

    async def test_equal_version_only_updates_if_timestamp_is_greater_than_current(
        self, task_run_id
    ):

        dt = pendulum.now("utc")
        await models.TaskRun.where(id=task_run_id).update(
            {"version": 10, "state_timestamp": dt, "state_message": "a"}
        )

        # same version, earlier timestamp
        await models.TaskRunState(
            task_run_id=task_run_id,
            version=10,
            timestamp=dt.subtract(seconds=1),
            start_time=dt,
            message="b",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"state_message", "state_timestamp"}
        )

        assert new_run.state_message == "a"
        assert new_run.state_timestamp == dt

        # same version, later timestamp
        await models.TaskRunState(
            task_run_id=task_run_id,
            version=10,
            timestamp=dt.add(seconds=1),
            start_time=dt,
            message="c",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"state_message", "state_timestamp"}
        )

        assert new_run.state_message == "c"
        assert new_run.state_timestamp == dt.add(seconds=1)

    async def test_trigger_updates_highest_version_when_multiple_states_inserted(
        self, task_run_id
    ):

        await models.TaskRun.where(id=task_run_id).update({"version": 10})
        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        dt = pendulum.now("UTC")

        await models.TaskRunState().insert_many(
            [
                dict(
                    task_run_id=task_run_id,
                    version=v,
                    timestamp=dt.add(seconds=v),
                    start_time=dt.add(seconds=v),
                    message="x",
                    result="y",
                    state="z",
                    serialized_state={"a": "b"},
                )
                for v in [1, 5, 10, 11, 12, 100]
            ]
        )

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "state_timestamp", "state_id"}
        )

        assert new_run.version == 100 != old_run.version
        assert new_run.state_id != old_run.state_id
        assert new_run.state_timestamp == dt.add(seconds=100)

    @pytest.mark.parametrize("original_version", [11, 100])
    async def test_trigger_does_not_update_run_when_when_state_version_is_lower(
        self, task_run_id, original_version
    ):

        await models.TaskRun.where(id=task_run_id).update({"version": original_version})

        old_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        dt = pendulum.now("UTC")

        await models.TaskRunState(
            task_run_id=task_run_id,
            version=10,
            timestamp=dt,
            start_time=dt,
            message="x",
            result="y",
            state="z",
            serialized_state={"a": "b"},
        ).insert()

        new_run = await models.TaskRun.where(id=task_run_id).first(
            {"version", "heartbeat", "state_id"}
        )

        assert new_run.version == old_run.version
        assert new_run.state_id == old_run.state_id
        assert new_run.heartbeat == old_run.heartbeat
