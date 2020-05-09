# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio
import json
import uuid

import pendulum
import pytest
from asynctest import CoroutineMock

import prefect
import prefect_server
from prefect.engine.state import Finished, Scheduled, Submitted, Success, Running
from prefect_server import config, api
from prefect_server.api import flows, runs, states
from prefect_server.database import models
from prefect_server.utilities import context
from prefect_server.utilities.exceptions import Unauthorized, NotFound
from prefect_server.utilities.tests import set_temporary_config
from prefect.utilities.graphql import EnumValue


@pytest.fixture
async def simple_flow_id():
    return await flows.create_flow(
        serialized_flow=prefect.Flow(name="test").serialize()
    )


class TestCreateRun:
    async def test_create_flow_run(self, simple_flow_id):
        flow_run_id = await runs.create_flow_run(flow_id=simple_flow_id)
        assert await models.FlowRun.exists(flow_run_id)

    async def test_create_flow_run_with_version_group_id(self):
        flow_ids = []
        for _ in range(15):
            flow_ids.append(
                await flows.create_flow(
                    serialized_flow=prefect.Flow(name="test").serialize(),
                    version_group_id="test-group",
                )
            )

        flow_id = flow_ids.pop(7)

        for fid in flow_ids:
            await flows.archive_flow(fid)

        flow_run_id = await runs.create_flow_run(version_group_id="test-group")
        fr = await models.FlowRun.where(id=flow_run_id).first({"flow": {"id": True}})

        assert fr.flow.id == flow_id

    async def test_create_flow_run_with_version_group_id_uses_latest_version(self,):
        flow_ids = []
        for _ in range(15):
            flow_ids.append(
                await flows.create_flow(
                    serialized_flow=prefect.Flow(name="test").serialize(),
                    version_group_id="test-group",
                )
            )

        first_id = flow_ids.pop(0)
        newer_id = flow_ids.pop(9)

        for fid in flow_ids:
            await flows.archive_flow(fid)

        flow_run_id = await runs.create_flow_run(version_group_id="test-group")
        fr = await models.FlowRun.where(id=flow_run_id).first({"flow": {"id": True}})

        assert fr.flow.id == newer_id

    async def test_create_flow_run_fails_if_neither_flow_nor_version_are_provided(
        self, simple_flow_id
    ):
        await flows.archive_flow(simple_flow_id)
        with pytest.raises(ValueError) as exc:
            await runs.create_flow_run(flow_id=None)
        assert "flow_id" in str(exc.value)
        assert "version_group_id" in str(exc.value)

    async def test_create_flow_run_fails_if_flow_is_archived(self, simple_flow_id):
        await flows.archive_flow(simple_flow_id)
        with pytest.raises(ValueError) as exc:
            await runs.create_flow_run(flow_id=simple_flow_id)
        assert "archived" in str(exc.value)

    async def test_create_flow_run_fails_if_all_versions_are_archived(self,):
        flow_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="test").serialize(),
            version_group_id="test-group",
        )
        await flows.archive_flow(flow_id)
        with pytest.raises(NotFound) as exc:
            await runs.create_flow_run(version_group_id="test-group")
        assert "no unarchived flows" in str(exc.value)

    async def test_create_flow_run_creates_name(self, simple_flow_id):
        flow_run_id_1 = await runs.create_flow_run(flow_id=simple_flow_id)
        flow_run_id_2 = await runs.create_flow_run(flow_id=simple_flow_id)
        flow_run_id_3 = await runs.create_flow_run(flow_id=simple_flow_id)
        flow_runs = await models.FlowRun.where(
            {"id": {"_in": [flow_run_id_1, flow_run_id_2, flow_run_id_3]}}
        ).get({"name"})

        assert isinstance(flow_runs[0].name, str)
        assert len(flow_runs[0].name) > 3
        # 3 different names
        assert len(set(fr.name for fr in flow_runs)) == 3

    async def test_create_flow_run_with_flow_run_name_creates_run_name(
        self, simple_flow_id
    ):
        flow_run_id_1 = await runs.create_flow_run(
            flow_id=simple_flow_id, flow_run_name="named flow run 1"
        )
        flow_run_id_2 = await runs.create_flow_run(
            flow_id=simple_flow_id, flow_run_name="named flow run 2"
        )
        flow_run_id_3 = await runs.create_flow_run(
            flow_id=simple_flow_id, flow_run_name="named flow run 3"
        )
        flow_runs = await models.FlowRun.where(
            {"id": {"_in": [flow_run_id_1, flow_run_id_2, flow_run_id_3]}}
        ).get({"name"})

        assert isinstance(flow_runs[0].name, str)
        assert len(flow_runs[0].name) > 3
        # 3 different names
        assert set(fr.name for fr in flow_runs) == {
            "named flow run 1",
            "named flow run 2",
            "named flow run 3",
        }

    async def test_create_run_with_missing_parameters_raises_error(self,):

        flow_id = await flows.create_flow(
            serialized_flow=prefect.Flow(
                name="test", tasks=[prefect.Parameter("x")]
            ).serialize(),
        )

        with pytest.raises(ValueError) as exc:
            await runs.create_flow_run(flow_id=flow_id)

        assert "Required parameters were not supplied" in str(exc.value)

    async def test_create_run_with_extra_parameters_raises_error(self, flow_id):
        with pytest.raises(ValueError) as exc:
            await runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1, y=2))
        assert "Extra parameters were supplied" in str(exc.value)

    async def test_create_run_with_parameters(self, flow_id):
        flow_run_id = await runs.create_flow_run(flow_id=flow_id, parameters=dict(x=1))

        flow_run = await models.FlowRun.where(id=flow_run_id).first({"parameters"})
        assert flow_run.parameters == dict(x=1)

    async def test_create_run_passes_start_time_to_flow_run_record(
        self, simple_flow_id
    ):
        dt = pendulum.datetime(2020, 1, 1)

        flow_run_id = await runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first(
            {"scheduled_start_time"}
        )

        assert flow_run.scheduled_start_time == dt

    async def test_create_run_defaults_auto_scheduled_to_false(self, simple_flow_id):
        dt = pendulum.datetime(2020, 1, 1)

        flow_run_id = await runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )

        flow_run = await models.FlowRun.where(id=flow_run_id).first(
            {"scheduled_start_time", "auto_scheduled"}
        )

        assert flow_run.scheduled_start_time == dt
        assert not flow_run.auto_scheduled

    async def test_new_run_has_scheduled_state(self, simple_flow_id):
        dt = pendulum.now()
        flow_run_id = await runs.create_flow_run(flow_id=simple_flow_id)
        fr = await models.FlowRun.where(id=flow_run_id).first(
            {"state", "state_start_time", "state_message"}
        )
        assert fr.state == "Scheduled"
        assert fr.state_start_time > dt
        assert fr.state_message == "Flow run scheduled."

    async def test_new_run_has_correct_state_start_time(self, simple_flow_id):
        dt = pendulum.datetime(2020, 1, 1)
        flow_run_id = await runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )
        fr = await models.FlowRun.where(id=flow_run_id).first({"state_start_time"})
        assert fr.state_start_time == dt

    async def test_new_run_state_is_in_history(self, simple_flow_id):
        dt = pendulum.datetime(2020, 1, 1)
        flow_run_id = await runs.create_flow_run(
            flow_id=simple_flow_id, scheduled_start_time=dt
        )
        frs = await models.FlowRunState.where(
            {"flow_run": {"id": {"_eq": flow_run_id}}}
        ).get(
            {"state", "start_time", "message"}, order_by={"timestamp": EnumValue("asc")}
        )
        assert len(frs) == 2
        assert frs[1].state == "Scheduled"
        assert frs[1].start_time == dt
        assert frs[1].message == "Flow run scheduled."

    async def test_create_flow_run_also_creates_task_runs(self,):

        flow_id = await flows.create_flow(
            serialized_flow=prefect.Flow(
                name="test", tasks=[prefect.Task(), prefect.Task(), prefect.Task()]
            ).serialize(),
        )

        flow_run_id = await runs.create_flow_run(flow_id=flow_id)

        assert (
            await models.TaskRun.where({"flow_run_id": {"_eq": flow_run_id}}).count()
            == 3
        )

    async def test_create_flow_run_also_creates_task_runs_with_cache_keys(self,):

        flow_id = await flows.create_flow(
            serialized_flow=prefect.Flow(
                name="test",
                tasks=[
                    prefect.Task(cache_key="test-key"),
                    prefect.Task(),
                    prefect.Task(cache_key="wat"),
                ],
            ).serialize(),
        )

        flow_run_id = await runs.create_flow_run(flow_id=flow_id)

        task_runs = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get({"cache_key"})

        assert set(tr.cache_key for tr in task_runs) == {"test-key", "wat", None}

    async def test_create_run_creates_context(self, simple_flow_id):
        flow_run_id = await runs.create_flow_run(flow_id=simple_flow_id)
        fr = await models.FlowRun.where(id=flow_run_id).first({"context"})
        assert fr.context == {}

    async def test_create_run_with_context(self, simple_flow_id):
        flow_run_id = await runs.create_flow_run(
            flow_id=simple_flow_id, context={"a": 1, "b": 2}
        )
        fr = await models.FlowRun.where(id=flow_run_id).first({"context"})
        assert fr.context["a"] == 1
        assert fr.context["b"] == 2


class TestGetTaskRunInfo:
    async def test_task_run(self, flow_run_id, task_id):
        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        assert await models.TaskRun.exists(tr_id)

    async def test_task_run_populates_cache_key(self, flow_run_id, task_id):
        cache_key = "test"
        # set the stage for creation with a cache_key
        await models.TaskRun.where({"task_id": {"_eq": task_id}}).delete()
        await models.Task.where(id=task_id).update(set={"cache_key": cache_key})

        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        task_run = await models.TaskRun.where(id=tr_id).first({"cache_key"})
        assert task_run.cache_key
        assert task_run.cache_key == cache_key

    async def test_task_run_does_not_populate_cache_key_unless_specified(
        self, flow_run_id, task_id
    ):
        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        task_run = await models.TaskRun.where(id=tr_id).first({"cache_key"})
        assert task_run.cache_key is None

    async def test_task_run_starts_in_pending_state(self, flow_run_id, task_id):
        tr_id_1 = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        tr_id_2 = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=12
        )
        trs = await models.TaskRun.where({"id": {"_in": [tr_id_1, tr_id_2]}}).get(
            {"state", "serialized_state"},
        )

        assert all(tr.state == "Pending" for tr in trs)
        assert all(tr.serialized_state["type"] == "Pending" for tr in trs)

    async def test_task_run_pulls_current_state(self, running_flow_run_id, task_id):
        tr_id = await runs.get_or_create_task_run(
            flow_run_id=running_flow_run_id, task_id=task_id, map_index=None
        )
        await states.set_task_run_state(tr_id, state=Running())

        tr = await models.TaskRun.where(id=tr_id).first({"state", "serialized_state"},)
        assert tr.state == "Running"
        assert tr.serialized_state["type"] == "Running"

    async def test_task_run_with_map_index_none_stored_as_negative_one(
        self, flow_run_id, task_id
    ):
        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        run = await models.TaskRun.where(id=tr_id).first(selection_set={"map_index"})
        assert run.map_index == -1

    async def test_task_run_with_map_index(self, flow_run_id, task_id):
        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=10
        )
        assert await models.TaskRun.exists(tr_id)

    async def test_task_run_fails_with_fake_flow_run_id(self, task_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await runs.get_or_create_task_run(
                flow_run_id=str(uuid.uuid4()), task_id=task_id, map_index=None
            )

    async def test_task_run_fails_with_fake_task_id(self, flow_run_id):
        with pytest.raises(ValueError, match="Invalid ID"):
            await runs.get_or_create_task_run(
                flow_run_id=flow_run_id, task_id=str(uuid.uuid4()), map_index=None
            )

    async def test_task_run_retrieves_existing_task_run(
        self, flow_run_id, task_id, task_run_id
    ):

        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        assert tr_id == task_run_id

    async def test_task_run_creates_new_task_run_for_map_index(
        self, flow_run_id, task_id
    ):
        existing_task_run_ids = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get("id")

        tr_id = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )

        # id not in previous ids
        assert tr_id not in {tr.id for tr in existing_task_run_ids}

        tr_count = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).count()
        assert tr_count == len(existing_task_run_ids) + 1

    async def test_task_run_creates_new_task_run_for_map_index_on_first_call_only(
        self, flow_run_id, task_id
    ):
        existing_task_run_ids = await models.TaskRun.where(
            {"flow_run_id": {"_eq": flow_run_id}}
        ).get("id")

        id_1 = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        id_2 = await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        assert id_1 not in {tr.id for tr in existing_task_run_ids}
        assert id_2 == id_1

    async def test_task_run_inserts_state_if_tr_doesnt_exist(
        self, flow_run_id, task_id
    ):
        task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        # call multiple times to be sure
        await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=1
        )
        await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=2
        )

        new_task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        assert new_task_run_state_count == task_run_state_count + 2

    async def test_task_run_doesnt_insert_state_if_tr_already_exists(
        self, flow_run_id, task_id, task_run_id
    ):
        task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        # call multiple times to be sure
        await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )
        await runs.get_or_create_task_run(
            flow_run_id=flow_run_id, task_id=task_id, map_index=None
        )

        new_task_run_state_count = await models.TaskRunState.where(
            {"task_run": {"flow_run_id": {"_eq": flow_run_id}}}
        ).count()

        assert new_task_run_state_count == task_run_state_count


class TestUpdateFlowRunHeartbeat:
    async def test_update_heartbeat(self, flow_run_id):
        dt = pendulum.now()
        run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert run.heartbeat is None

        await runs.update_flow_run_heartbeat(flow_run_id=flow_run_id)

        run = await models.FlowRun.where(id=flow_run_id).first({"heartbeat"})
        assert dt < run.heartbeat

    async def test_update_heartbeat_with_bad_id(self):
        with pytest.raises(ValueError) as exc:
            await runs.update_flow_run_heartbeat(flow_run_id=str(uuid.uuid4()))
        assert "Invalid" in str(exc.value)


class TestUpdateTaskRunHeartbeat:
    async def test_update_heartbeat(self, task_run_id):
        dt = pendulum.now()
        run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert run.heartbeat is None

        dt1 = pendulum.now()
        await runs.update_task_run_heartbeat(task_run_id=task_run_id)

        run = await models.TaskRun.where(id=task_run_id).first({"heartbeat"})
        assert dt1 < run.heartbeat

    async def test_update_heartbeat_with_bad_id(self):
        with pytest.raises(ValueError) as exc:
            await runs.update_task_run_heartbeat(task_run_id=str(uuid.uuid4()))
        assert "Invalid" in str(exc.value)


class TestGetRunsInQueue:
    async def test_get_flow_run_in_queue(
        self, flow_run_id,
    ):

        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await runs.get_runs_in_queue()
        assert flow_run_id in flow_runs

    async def test_get_flow_run_in_queue_uses_labels(
        self, flow_run_id, labeled_flow_run_id,
    ):

        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await runs.get_runs_in_queue(labels=["foo", "bar"])
        assert labeled_flow_run_id in flow_runs
        assert flow_run_id not in flow_runs

    async def test_get_flow_run_in_queue_works_if_environment_labels_are_none(
        self, flow_run_id, flow_id
    ):
        """
        Old environments have no labels attribute, so we ensure labels are loaded as a list
        even if the labels attribute is `None`. This test would fail if `None` were loaded
        improperly.
        """

        flow = await models.Flow.where(id=flow_id).first({"environment"})
        flow.environment["labels"] = None
        await models.Flow.where(id=flow_id).update({"environment": flow.environment})
        check_flow = await models.Flow.where(id=flow_id).first({"environment"})
        assert check_flow.environment["labels"] is None

        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        await runs.get_runs_in_queue(labels=["foo", "bar"])

    async def test_get_flow_run_in_queue_works_if_environment_labels_are_missing(
        self, flow_run_id, flow_id
    ):
        """
        Old environments have no labels attribute, so we ensure labels are loaded as a list
        even if the labels attribute is missing. This test would fail if it were loaded
        improperly.
        """

        flow = await models.Flow.where(id=flow_id).first({"environment"})
        del flow.environment["labels"]
        await models.Flow.where(id=flow_id).update({"environment": flow.environment})
        check_flow = await models.Flow.where(id=flow_id).first({"environment"})
        assert "labels" not in check_flow.environment

        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await runs.get_runs_in_queue(labels=["foo", "bar"])

    async def test_get_flow_run_in_queue_filters_labels_correctly(
        self, flow_run_id, labeled_flow_run_id,
    ):

        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await states.set_flow_run_state(
            flow_run_id=labeled_flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        super_flow_runs = await runs.get_runs_in_queue(labels=["foo", "bar", "chris"])
        random_flow_runs = await runs.get_runs_in_queue(labels=["dev"])
        mixed_flow_runs = await runs.get_runs_in_queue(labels=["foo", "staging"])
        assert labeled_flow_run_id in super_flow_runs
        assert flow_run_id not in super_flow_runs

        assert labeled_flow_run_id not in random_flow_runs
        assert flow_run_id not in random_flow_runs

        assert labeled_flow_run_id not in mixed_flow_runs
        assert flow_run_id not in mixed_flow_runs

    async def test_get_flow_run_in_queue_uses_labels_on_task_runs(
        self, flow_run_id, labeled_flow_run_id, labeled_task_run_id, task_run_id,
    ):

        await states.set_task_run_state(
            task_run_id=labeled_task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await states.set_task_run_state(
            task_run_id=task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await runs.get_runs_in_queue(labels=["foo", "bar"])
        assert labeled_flow_run_id in flow_runs
        assert flow_run_id not in flow_runs

    async def test_get_flow_run_in_queue_filters_labels_on_task_runs_correctly(
        self, flow_run_id, labeled_flow_run_id, labeled_task_run_id, task_run_id,
    ):

        await states.set_task_run_state(
            task_run_id=labeled_task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )
        await states.set_task_run_state(
            task_run_id=task_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        super_flow_runs = await runs.get_runs_in_queue(labels=["foo", "bar", "chris"])
        random_flow_runs = await runs.get_runs_in_queue(labels=["dev"])
        mixed_flow_runs = await runs.get_runs_in_queue(labels=["foo", "staging"])
        assert labeled_flow_run_id in super_flow_runs
        assert flow_run_id not in super_flow_runs

        assert labeled_flow_run_id not in random_flow_runs
        assert flow_run_id not in random_flow_runs

        assert labeled_flow_run_id not in mixed_flow_runs
        assert flow_run_id not in mixed_flow_runs

    async def test_get_flow_run_in_queue_before_certain_time(
        self, flow_run_id,
    ):

        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").subtract(days=1)),
        )

        flow_runs = await runs.get_runs_in_queue()
        assert flow_run_id in flow_runs

        flow_runs = await runs.get_runs_in_queue(
            before=pendulum.now("utc").subtract(days=2)
        )
        assert flow_run_id not in flow_runs

    async def test_get_multiple_flow_run_in_queue_before_certain_time(
        self, flow_id,
    ):
        now = pendulum.now("utc")

        await models.FlowRun.where().delete()

        for i in range(10):
            await runs.create_flow_run(
                flow_id=flow_id, scheduled_start_time=now.add(minutes=i)
            )

        flow_runs = await runs.get_runs_in_queue(before=now.add(minutes=4))

        assert len(flow_runs) == 5

    async def test_get_flow_run_in_queue_matches_limit(self, flow_id):

        concurrency = config.queued_runs_returned_limit

        # create more runs than concurrency allows
        for i in range(concurrency * 2):
            await runs.create_flow_run(flow_id=flow_id)

        flow_runs = await runs.get_runs_in_queue()

        assert len(flow_runs) == concurrency

    async def test_number_queued_runs_returned_is_capped_by_config_value(self, flow_id):

        # create more runs than concurrency allows
        for _ in range(2 * config.queued_runs_returned_limit):
            await runs.create_flow_run(flow_id=flow_id)

        flow_runs = await runs.get_runs_in_queue()

        # confirm there are enough items for the cap to be enforced
        assert len(flow_runs) == config.queued_runs_returned_limit

    async def test_future_flow_runs_are_not_retrieved(
        self, flow_run_id,
    ):

        await models.FlowRun.where({"id": {"_neq": flow_run_id}}).delete()
        await states.set_flow_run_state(
            flow_run_id=flow_run_id,
            state=Scheduled(start_time=pendulum.now("utc").add(days=1)),
        )

        assert not await runs.get_runs_in_queue()
