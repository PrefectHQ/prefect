# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import uuid

import pendulum
import pytest

import prefect
from prefect.engine.state import Scheduled, Submitted, Running
from prefect_server import api, config
from prefect_server.database import models
from prefect_server.utilities.exceptions import Unauthenticated, Unauthorized
from prefect_server.utilities.tests import set_temporary_config


class TestCreateFlowRun:
    mutation = """
        mutation($input: create_flow_run_input!) {
            create_flow_run(input: $input) {
                id
            }
        }
    """

    async def test_create_flow_run(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=flow_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "parameters",
                "scheduled_start_time",
                "auto_scheduled",
                "context",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.scheduled_start_time == dt
        assert fr.parameters == dict(x=1)
        assert fr.auto_scheduled is False
        assert fr.context == {"a": 2}

    async def test_create_flow_run_with_version_group_id(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)
        f = await models.Flow.where(id=flow_id).first({"version_group_id"})
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=None,
                    version_group_id=f.version_group_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "parameters",
                "scheduled_start_time",
                "auto_scheduled",
                "context",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.scheduled_start_time == dt
        assert fr.parameters == dict(x=1)
        assert fr.auto_scheduled is False
        assert fr.context == {"a": 2}

    async def test_create_flow_run_with_run_name(self, run_query, flow_id):
        dt = pendulum.now("utc").add(hours=1)
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(
                    flow_id=flow_id,
                    parameters=dict(x=1),
                    context=dict(a=2),
                    scheduled_start_time=dt.isoformat(),
                    flow_run_name="named flow run",
                )
            ),
        )
        fr = await models.FlowRun.where(id=result.data.create_flow_run.id).first(
            {
                "flow_id",
                "parameters",
                "scheduled_start_time",
                "auto_scheduled",
                "context",
                "name",
            }
        )
        assert fr.flow_id == flow_id
        assert fr.scheduled_start_time == dt
        assert fr.parameters == dict(x=1)
        assert fr.auto_scheduled is False
        assert fr.context == {"a": 2}
        assert fr.name == "named flow run"

    async def test_create_flow_run_fails_for_archived_flow(self, run_query, flow_id):
        await api.flows.archive_flow(flow_id)
        dt = pendulum.now("utc").add(hours=1)
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=flow_id, parameters=dict(x=1))),
        )
        assert "archived" in result.errors[0].message

    async def test_create_flow_run_without_parameters_raises_error(self, run_query):

        serialized_flow = prefect.Flow(
            name="test", tasks=[prefect.Parameter("x")]
        ).serialize(build=False)
        create_flow_mutation = """
            mutation($input: create_flow_input!) {
                create_flow(input: $input) {
                    id
                }
            }
        """
        result = await run_query(
            query=create_flow_mutation,
            variables=dict(input=dict(serialized_flow=serialized_flow)),
        )

        pendulum.now("utc")
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_id=result.data.create_flow.id)),
        )
        assert result.data.create_flow_run is None
        assert "Required parameters" in result.errors[0].message


class TestGetOrCreateTaskRun:
    mutation = """
        mutation($input: get_or_create_task_run_input!) {
            get_or_create_task_run(input: $input) {
                id
            }
        }
    """

    async def test_get_or_create_task_run(
        self, run_query, task_run_id, task_id, flow_run_id
    ):
        n_tr = await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=flow_run_id, task_id=task_id)),
        )

        assert result.data.get_or_create_task_run.id == task_run_id
        assert (
            await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
            == n_tr
        )

    async def test_get_or_create_task_run_new_task_run(
        self, run_query, task_run_id, task_id, flow_run_id
    ):
        n_tr = await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(flow_run_id=flow_run_id, task_id=task_id, map_index=10)
            ),
        )

        assert result.data.get_or_create_task_run.id != task_run_id
        assert (
            await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
            == n_tr + 1
        )


class TestUpdateFlowRunHeartbeat:
    mutation = """
        mutation($input: update_flow_run_heartbeat_input!) {
            update_flow_run_heartbeat(input: $input) {
                success
            }
        }
    """

    async def test_update_flow_run_heartbeat(self, run_query, flow_run_id):
        dt = pendulum.now()
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(flow_run_id=flow_run_id)),
        )

        # sleep to give the concurrent update a chance to run
        await asyncio.sleep(0.1)
        run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})

        assert result.data.update_flow_run_heartbeat.success
        assert dt < run.heartbeat

    async def test_update_flow_run_heartbeat_invalid_id_returns_success(
        self, run_query
    ):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=str(uuid.uuid4()))),
        )

        assert result.data.update_flow_run_heartbeat.success


class TestUpdateTaskRunHeartbeat:
    mutation = """
        mutation($input: update_task_run_heartbeat_input!) {
            update_task_run_heartbeat(input: $input) {
                success
            }
        }
    """

    async def test_update_task_run_heartbeat(self, run_query, task_run_id):
        dt = pendulum.now()
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(task_run_id=task_run_id)),
        )

        # sleep to give the concurrent update a chance to run
        await asyncio.sleep(0.1)
        run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})

        assert result.data.update_task_run_heartbeat.success
        assert dt < run.heartbeat

    async def test_update_task_run_heartbeat_invalid_id_is_still_success(
        self, run_query,
    ):
        pendulum.now()
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(task_run_id=str(uuid.uuid4()))),
        )

        assert result.data.update_task_run_heartbeat.success


class TestDeleteFlowRun:
    mutation = """
        mutation($input: delete_flow_run_input!) {
            delete_flow_run(input: $input) {
                success
            }
        }
    """

    async def test_delete_flow_run(self, run_query, flow_run_id):
        result = await run_query(
            query=self.mutation, variables=dict(input=dict(flow_run_id=flow_run_id)),
        )

        assert result.data.delete_flow_run.success
        assert not await models.FlowRun.exists(flow_run_id)

    async def test_delete_flow_run_bad_id(self, run_query):
        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(flow_run_id=str(uuid.uuid4()))),
        )

        assert not result.data.delete_flow_run.success


class TestGetRunsInQueue:
    mutation = """
        mutation($input: get_runs_in_queue_input!) {
            get_runs_in_queue(input: $input) {
                flow_run_ids
            }
        }
    """

    async def test_get_runs_in_queue(
        self, run_query, flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(query=self.mutation, variables=dict(input=dict()))
        assert flow_run_id in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_uses_labels(
        self, run_query, flow_run_id, labeled_flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(labels=["foo", "bar"])),
        )
        assert labeled_flow_run_id in result.data.get_runs_in_queue.flow_run_ids
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_uses_labels_and_filters_for_subset(
        self, run_query, flow_run_id, labeled_flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(input=dict(labels=["foo", "bar", "extra"])),
        )
        assert labeled_flow_run_id in result.data.get_runs_in_queue.flow_run_ids
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_uses_labels_for_task_runs(
        self, run_query, flow_run_id, labeled_flow_run_id, labeled_task_run_id,
    ):
        await api.states.set_task_run_state(
            task_run_id=labeled_task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation, variables=dict(input=dict(labels=["foo", "bar"])),
        )
        assert labeled_flow_run_id in result.data.get_runs_in_queue.flow_run_ids
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_get_runs_in_queue_before_certain_time(
        self, run_query, flow_run_id,
    ):
        await api.states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        result = await run_query(
            query=self.mutation,
            variables=dict(
                input=dict(before=pendulum.now("utc").subtract(days=2).isoformat(),)
            ),
        )
        assert flow_run_id not in result.data.get_runs_in_queue.flow_run_ids

    async def test_multiple_runs_in_queue_before_certain_time(
        self, run_query, flow_id,
    ):
        now = pendulum.now("utc")

        # delete all other flow runs
        await models.FlowRun.where().delete()

        for i in range(10):
            await api.runs.create_flow_run(
                flow_id=flow_id, scheduled_start_time=now.add(minutes=i)
            )

        for i in range(10):
            result = await run_query(
                query=self.mutation,
                variables=dict(
                    input=dict(before=pendulum.now("utc").add(minutes=i).isoformat(),)
                ),
            )
            assert len(result.data.get_runs_in_queue.flow_run_ids) == i + 1
