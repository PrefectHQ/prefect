# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import uuid

import pytest

import prefect
import prefect_server
from prefect_server.api import flows, runs, schedules, states
from prefect_server.database import models as m
from prefect_server.utilities import context


@pytest.fixture
def flow():
    flow = prefect.Flow(name="my flow")
    flow.add_edge(
        prefect.Task("t1", tags={"red", "blue"}),
        prefect.Task("t2", cache_key="test-key", tags={"red", "green"}),
    )
    flow.add_task(prefect.Parameter("x", default=1))
    mapped_task = prefect.Task("t3", tags={"mapped"})
    flow.add_edge(prefect.Parameter("y"), mapped_task, key="y", mapped=True)
    flow.add_edge(prefect.Task("t4"), mapped_task, key="not_mapped")
    return flow


class TestCreateFlow:
    async def test_create_flow(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        assert await m.Flow.exists(flow_id)

    async def test_create_invalid_flow_provides_helpful_error(self, flow):
        serialized_flow = flow.serialize()
        for idx, task in enumerate(serialized_flow["tasks"]):
            if task["name"] == "t4":
                serialized_flow["tasks"][idx]["retry_delay"] = 3
        with pytest.raises(ValueError) as exc:
            await flows.create_flow(serialized_flow=serialized_flow)
        assert "Invalid flow" in repr(exc.value)
        assert "greater than 0 must be provided if specifying a retry delay" in repr(
            exc.value
        )

    async def test_create_flow_is_not_archived(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived

    async def test_create_empty_flow(self):
        flow_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="test").serialize()
        )
        assert await m.Flow.exists(flow_id)

    async def test_create_flow_without_edges(self):
        flow = prefect.Flow(name="test")
        flow.add_task(prefect.Task())
        flow.add_task(prefect.Task())

        flow_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="test").serialize()
        )
        assert await m.Flow.exists(flow_id)

    async def test_create_flow_also_creates_tasks(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Flow.where(id=flow_id).first(
            {"tasks_aggregate": {"aggregate": {"count"}}}, apply_schema=False
        )
        assert result.tasks_aggregate.aggregate.count == len(flow.tasks)

    async def test_create_flow_saves_task_triggers(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Flow.where(id=flow_id).first({"tasks": {"trigger"}})
        assert "prefect.triggers.all_successful" in {t.trigger for t in result.tasks}

    async def test_create_flow_saves_custom_task_triggers(self, flow):

        task = list(flow.tasks)[0]
        task.trigger = flows.create_flow

        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Flow.where(id=flow_id).first({"tasks": {"trigger"}})
        assert "prefect_server.api.flows.create_flow" in {
            t.trigger for t in result.tasks
        }

    async def test_create_flow_also_creates_tasks_with_cache_keys(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Flow.where(id=flow_id).first({"tasks": {"cache_key"}})
        assert "test-key" in {t.cache_key for t in result.tasks}

    async def test_create_flow_tracks_mapped_tasks(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Flow.where(id=flow_id).first({"tasks": {"mapped"}})
        assert True in {t.mapped for t in result.tasks}

    async def test_create_flow_tracks_root_tasks(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_root_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"t1", "t4", "x", "y"}

    async def test_create_flow_tracks_terminal_tasks(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_terminal_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"x", "t2", "t3"}

    async def test_create_flow_tracks_reference_tasks(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_reference_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"x", "t2", "t3"}

    async def test_create_flow_tracks_updated_reference_tasks(self, flow):
        t3 = flow.get_tasks(name="t3")[0]
        t4 = flow.get_tasks(name="t4")[0]
        flow.set_reference_tasks([t3, t4])

        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        result = await m.Task.where(
            {"flow_id": {"_eq": flow_id}, "is_reference_task": {"_eq": True}}
        ).get({"name"})
        assert set([t.name for t in result]) == {"t3", "t4"}

    async def test_flows_can_be_safely_created_twice(self, flow):
        """
        Because object ids are not the same as database ids, the same flow can be uploaded twice
        """
        flow_id_1 = await flows.create_flow(serialized_flow=flow.serialize())
        flow_id_2 = await flows.create_flow(serialized_flow=flow.serialize())

        assert flow_id_1 != flow_id_2

        assert await m.Flow.where({"id": {"_in": [flow_id_1, flow_id_2]}}).count() == 2
        assert (
            await m.Task.where({"flow_id": {"_in": [flow_id_1, flow_id_2]}}).count()
            == len(flow.tasks) * 2
        )

    async def test_create_flow_with_schedule(self):
        flow = prefect.Flow(
            name="test", schedule=prefect.schedules.CronSchedule("0 0 * * *")
        )
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        schedule = await m.Schedule.where({"flow_id": {"_eq": flow_id}}).first(
            {"schedule"}
        )

        schedule.schedule = prefect.serialization.schedule.ScheduleSchema().load(
            schedule.schedule
        )

        assert len(schedule.schedule.clocks) == 1
        assert isinstance(
            schedule.schedule.clocks[0], prefect.schedules.clocks.CronClock
        )

    async def test_create_flow_with_schedule_is_active(self):
        flow = prefect.Flow(
            name="test", schedule=prefect.schedules.CronSchedule("0 0 * * *")
        )
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())
        schedule = await m.Schedule.where({"flow_id": {"_eq": flow_id}}).first(
            {"active"}
        )
        assert schedule.active

    async def test_create_flow_with_inactive_schedule(self):
        flow = prefect.Flow(
            name="test", schedule=prefect.schedules.CronSchedule("0 0 * * *")
        )
        flow_id = await flows.create_flow(
            serialized_flow=flow.serialize(), set_schedule_active=False,
        )
        schedule = await m.Schedule.where({"flow_id": {"_eq": flow_id}}).first(
            {"active"}
        )
        assert not schedule.active

    async def test_parameter_handling(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        f = await m.Flow.where(id=flow_id).first({"parameters"})

        f.parameters = prefect.serialization.task.ParameterSchema().load(
            f.parameters, many=True
        )
        assert isinstance(f.parameters, list)
        assert all([isinstance(p, prefect.Parameter) for p in f.parameters])
        assert len(f.parameters) == len(flow.parameters())
        assert {p.name for p in f.parameters} == {"x", "y"}
        assert {p.default for p in f.parameters} == {None, 1}
        assert {p.required for p in f.parameters} == {True, False}

    async def test_create_flow_assigns_description(self, flow):
        description = "test"
        flow_id = await flows.create_flow(
            serialized_flow=flow.serialize(), description=description,
        )
        flow = await m.Flow.where(id=flow_id).first("description")
        assert flow.description == description

    async def test_create_flow_intelligently_handles_scheduled_param_defaults(self):
        a, b = prefect.Parameter("a"), prefect.Parameter("b", default=1)
        clock = prefect.schedules.clocks.CronClock(
            cron=f"* * * * *", parameter_defaults={"a": 1, "b": 2}
        )
        schedule = prefect.schedules.Schedule(clocks=[clock])

        flow = prefect.Flow("test-params", tasks=[a, b], schedule=schedule)

        flow_id = await flows.create_flow(serialized_flow=flow.serialize())
        assert flow_id

    async def test_create_flow_persists_serialized_flow(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        persisted_flow = await m.Flow.where(id=flow_id).first({"serialized_flow"})
        # confirm the keys in the serialized flow match the form we'd expect
        assert persisted_flow.serialized_flow == flow.serialize()


class TestCreateFlowVersions:
    async def test_create_flow_assigns_random_version_group_id(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        flow_model = await m.Flow.where(id=flow_id).first(
            {"version_group_id", "version"}
        )
        assert flow_model.version_group_id
        assert flow_model.version == 1

    async def test_version_auto_increments_for_same_version_group(self):
        flow_1_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="test").serialize()
        )
        flow_1 = await m.Flow.where(id=flow_1_id).first({"version_group_id", "version"})

        flow2_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="a different test").serialize(),
            version_group_id=flow_1.version_group_id,
        )

        flow_2 = await m.Flow.where(id=flow2_id).first({"version_group_id", "version"})
        assert flow_1.version_group_id == flow_2.version_group_id
        assert flow_1.version == 1
        assert flow_2.version == 2

    async def test_custom_version_group_id(self):
        flow_1_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="test").serialize(),
            version_group_id="hello",
        )

        flow2_id = await flows.create_flow(
            serialized_flow=prefect.Flow(name="a different test").serialize(),
            version_group_id="hello",
        )

        flow_1 = await m.Flow.where(id=flow_1_id).first({"version_group_id", "version"})
        flow_2 = await m.Flow.where(id=flow2_id).first({"version_group_id", "version"})
        assert flow_1.version_group_id == flow_2.version_group_id == "hello"
        assert flow_1.version == 1
        assert flow_2.version == 2

    async def test_create_flow_with_tags(self, flow):
        flow_id = await flows.create_flow(serialized_flow=flow.serialize())

        db_tasks = await m.Task.where({"flow_id": {"_eq": flow_id}}).get(
            {"name", "tags"}
        )

        for task in db_tasks:
            if task.name == "t1":
                assert isinstance(task.tags, list)
                assert set(task.tags) == {"red", "blue"}
            elif task.name == "t2":
                assert set(task.tags) == {"red", "green"}
            elif task.name == "t3":
                assert task.tags == ["mapped"]
            else:
                assert task.tags == []


class TestArchive:
    async def test_archive_flow(self, flow_id):
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await flows.archive_flow(flow_id)
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived

    async def test_archive_flow_twice(self, flow_id):
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await flows.archive_flow(flow_id)
        await flows.archive_flow(flow_id)
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived

    async def test_archive_flow_deletes_scheduled_runs(self, flow_id):
        # create scheduled runs since the fixture doesn't

        schedule = await m.Schedule.where({"flow_id": {"_eq": flow_id}}).first({"id"})
        await schedules.schedule_flow_runs(schedule_id=schedule.id)

        scheduled_runs = await m.FlowRun.where(
            {"flow_id": {"_eq": flow_id}, "state": {"_eq": "Scheduled"}}
        ).get({"id"})
        assert scheduled_runs

        await flows.archive_flow(flow_id)

        assert (
            await m.FlowRun.where(
                {"id": {"_in": [r.id for r in scheduled_runs]}}
            ).count()
            == 0
        )

    async def test_archive_flow_resets_last_scheduled_time(self, flow_id):

        await flows.archive_flow(flow_id)

        s = await m.Schedule.where({"flow_id": {"_eq": flow_id}}).first(
            {"last_scheduled_run_time"}
        )
        assert s.last_scheduled_run_time is None

    async def test_archive_flow_with_bad_id(self, flow_id):
        assert not await flows.archive_flow(str(uuid.uuid4()))

    async def test_archive_flow_with_none_id(self, flow_id):
        with pytest.raises(ValueError, match="Must provide flow ID."):
            await flows.archive_flow(flow_id=None)


class TestUnarchiveFlow:
    async def test_unarchive_flow(self, flow_id):
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await flows.archive_flow(flow_id)
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived
        await flows.unarchive_flow(flow_id)
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived

    async def test_unarchive_flow_twice(self, flow_id):
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived
        await flows.archive_flow(flow_id)
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert flow.archived
        await flows.unarchive_flow(flow_id)
        await flows.unarchive_flow(flow_id)
        flow = await m.Flow.where(id=flow_id).first({"archived"})
        assert not flow.archived

    async def test_unarchive_flow_with_bad_id(self, flow_id):
        assert not await flows.unarchive_flow(str(uuid.uuid4()))

    async def test_unarchive_flow_with_none_id(self, flow_id):
        with pytest.raises(ValueError, match="Must provide flow ID."):
            await flows.unarchive_flow(flow_id=None)


class TestDeleteFlow:
    async def test_delete_flow_deletes_schedule(self, flow_id):
        n_schedules = await m.Schedule.where({}).count()
        assert await flows.delete_flow(flow_id)
        assert await m.Schedule.where({}).count() == n_schedules - 1

    async def test_delete_flow_deletes_flow_runs(self, flow_id, flow_run_id):
        await states.set_flow_run_state(
            flow_run_id=flow_run_id, state=prefect.engine.state.Scheduled()
        )

        assert await m.FlowRun.exists(flow_run_id)

        assert await flows.delete_flow(flow_id)

        assert not await m.FlowRun.exists(flow_run_id)

    async def test_delete_flow_with_none_id(self):
        with pytest.raises(ValueError, match="Must provide flow ID."):
            await flows.delete_flow(flow_id=None)


class TestUpdateFlowHeartbeat:
    async def test_disable_heartbeat_for_flow(self, flow_id):
        await m.Flow.where(id=flow_id).update({"settings": {}})
        flow = await m.Flow.where(id=flow_id).first({"settings"})

        assert flow.settings == {}
        assert await flows.disable_heartbeat_for_flow(flow_id=flow_id)

        flow = await m.Flow.where(id=flow_id).first({"settings"})
        assert flow.settings["heartbeat_enabled"] is False
        assert flow.settings["disable_heartbeat"] is True

    async def test_enable_heartbeat_for_flow(self, flow_id):
        await m.Flow.where(id=flow_id).update({"settings": {}})
        flow = await m.Flow.where(id=flow_id).first({"settings"})

        assert flow.settings == {}
        assert await flows.enable_heartbeat_for_flow(flow_id=flow_id)

        flow = await m.Flow.where(id=flow_id).first({"settings"})
        assert flow.settings["heartbeat_enabled"] is True
        assert flow.settings["disable_heartbeat"] is False

    async def test_disable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await flows.disable_heartbeat_for_flow(flow_id=None)

    async def test_enable_heartbeat_for_flow_with_none_flow_id(self):
        with pytest.raises(ValueError, match="Invalid flow ID"):
            await flows.enable_heartbeat_for_flow(flow_id=None)
