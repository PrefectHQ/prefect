import pytest
import datetime
import prefect
from prefect.core import Task, Flow, Edge
from prefect.serialization.schemas import core


class TestTask:
    def test_serialize_empty_dict(self):
        assert core.TaskSchema().dump({})

    def test_deserialize_empty_dict(self):
        t = core.TaskSchema().load({})
        assert isinstance(t, Task)

    def test_serialize_task(self):
        assert isinstance(core.TaskSchema().dump(Task()), dict)

    def test_deserialize_task(self):
        task = Task(
            name="hi",
            slug="hi-1",
            description="hello",
            max_retries=5,
            retry_delay=datetime.timedelta(seconds=5),
            timeout=datetime.timedelta(minutes=1),
            trigger=prefect.triggers.all_failed,
            skip_on_upstream_skip=False,
            cache_for=datetime.timedelta(hours=1),
        )
        deserialized = core.TaskSchema().load(core.TaskSchema().dump(task))
        assert isinstance(deserialized, Task)
        for key in [
            "name",
            "slug",
            "description",
            "max_retries",
            "retry_delay",
            "timeout",
            "trigger",
            "skip_on_upstream_skip",
            "cache_for",
        ]:
            assert getattr(task, key) == getattr(deserialized, key)

    def test_deserialize_task_subclass_is_task_but_not_task_subclass(self):
        class NewTask(Task):
            pass

        serialized = core.TaskSchema().dump(NewTask())
        assert serialized["type"].endswith("<locals>.NewTask")

        deserialized = core.TaskSchema().load(serialized)
        assert isinstance(deserialized, Task)
        assert not isinstance(deserialized, NewTask)

    def test_serialize_task_with_id(self):
        t = Task()
        context = dict(task_ids={t: "xyz"})
        serialized = core.TaskSchema(context=context).dump(t)
        assert serialized["id"] == "xyz"

    def test_deserialize_task_with_id(self):
        """
        When tasks are deserialized, they put their ID in a special task_cache in context
        so it can be reused elsewhere.
        """
        t = Task()
        context = dict(task_ids={t: "xyz"})
        serialized = core.TaskSchema(context=context).dump(t)
        deserialized = core.TaskSchema(context=context).load(serialized)
        assert "task_cache" in context
        assert context["task_cache"]["xyz"] is deserialized

    def test_deserializing_tasks_with_ids_reuses_task_cache_to_recreate_object(self):
        """
        If an id is found in the task cache, the corresponding object is loaded
        """
        t = Task()
        context = dict(task_ids={t: "xyz"}, task_cache={"xyz": t})
        serialized = core.TaskSchema(context=context).dump(t)
        deserialized = core.TaskSchema(context=context).load(serialized)
        assert deserialized is t


class TestEdge:
    def test_serialize_empty_dict(self):
        assert core.EdgeSchema().dump({})

    def test_deserialize_empty_dict_fails(self):
        with pytest.raises(TypeError) as exc:
            core.EdgeSchema().load({})
        assert "required positional arguments" in str(exc).lower()

    def test_deserialize_empty_dict_without_create_object(self):
        t = core.EdgeSchema().load({}, create_object=False)

    def test_serialize_edge(self):
        assert isinstance(core.EdgeSchema().dump(Edge(Task(), Task())), dict)

    def test_serialize_edge_only_records_task_id(self):
        t1, t2 = Task("t1"), Task("t2")
        serialized = core.EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
        assert serialized["upstream_task"] == {
            "id": None,
            "__version__": prefect.__version__,
        }
        assert serialized["downstream_task"] == {
            "id": None,
            "__version__": prefect.__version__,
        }

    def test_deserialize_edge(self):
        t1, t2 = Task("t1"), Task("t2")
        serialized = core.EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
        deserialized = core.EdgeSchema().load(serialized)
        assert isinstance(deserialized, Edge)
        assert deserialized.key == "x"
        assert deserialized.mapped is True

    def test_deserialize_edge_has_no_task_info(self):
        """
        Edges only serialize task IDs (if available), so the task names will revert to default.
        """
        t1, t2 = Task("t1"), Task("t2")
        serialized = core.EdgeSchema().dump(Edge(t1, t2, key="x", mapped=True))
        deserialized = core.EdgeSchema().load(serialized)

        assert deserialized.upstream_task.name is "Task"
        assert deserialized.downstream_task.name is "Task"

    def test_deserialize_edge_uses_task_ids(self):
        """
        If a Task ID context is available, the task attributes will use it
        """
        t1, t2 = Task("t1"), Task("t2")
        context = dict(task_ids={t1: "t1", t2: "t2"})

        serialized = core.EdgeSchema(context=context).dump(
            Edge(t1, t2, key="x", mapped=True)
        )
        assert serialized["upstream_task"]["id"] == "t1"
        assert serialized["downstream_task"]["id"] == "t2"

    def test_deserialize_edge_uses_task_cache(self):
        """
        If a Task Cache is available, the task attributes will use it
        """
        t1, t2 = Task("t1"), Task("t2")
        context = dict(task_ids={t1: "t1", t2: "t2"}, task_cache={"t1": t1, "t2": t2})
        serialized = core.EdgeSchema(context=context).dump(
            Edge(t1, t2, key="x", mapped=True)
        )
        deserialized = core.EdgeSchema(context=context).load(serialized)

        assert deserialized.upstream_task is t1
        assert deserialized.downstream_task is t2


class TestFlow:
    def test_serialize_empty_dict(self):
        assert core.FlowSchema().dump({})

    def test_deserialize_empty_dict(self):
        assert isinstance(core.FlowSchema().load({}), Flow)

    def test_serialize_flow(self):
        serialized = core.FlowSchema().dump(
            Flow(name="n", project="p", description="d")
        )
        assert serialized["name"] == "n"
        assert serialized["project"] == "p"
        assert serialized["description"] == "d"

    def test_deserialize_flow(self):
        serialized = core.FlowSchema().dump(
            Flow(name="n", project="p", description="d")
        )
        deserialized = core.FlowSchema().load(serialized)
        assert isinstance(deserialized, Flow)
        assert deserialized.name == "n"
        assert deserialized.project == "p"
        assert deserialized.description == "d"

    def test_deserialize_flow_subclass_is_flow_but_not_flow_subclass(self):
        class NewFlow(Flow):
            pass

        serialized = core.FlowSchema().dump(NewFlow())
        assert serialized["type"].endswith("<locals>.NewFlow")

        deserialized = core.FlowSchema().load(serialized)
        assert isinstance(deserialized, Flow)
        assert not isinstance(deserialized, NewFlow)

    def test_deserialize_schedule(self):
        schedule = prefect.schedules.CronSchedule("* * 0 0 0")
        f = Flow(schedule=schedule)
        serialized = core.FlowSchema().dump(f)
        deserialized = core.FlowSchema().load(serialized)
        assert deserialized.schedule.next(5) == f.schedule.next(5)

    def test_deserialize_id(self):
        f = Flow()
        serialized = core.FlowSchema().dump(f)
        deserialized = core.FlowSchema().load(serialized)
        assert deserialized.id == f.id

    def test_deserialize_tasks(self):
        tasks = [Task(n) for n in ["a", "b", "c"]]
        f = Flow(tasks=tasks)
        serialized = core.FlowSchema().dump(f)
        deserialized = core.FlowSchema().load(serialized)
        assert len(deserialized.tasks) == len(f.tasks)

    def test_deserialize_edges(self):
        """
        Tests that edges are appropriately deserialized, even in they involve keys.
        Also tests that tasks are deserialized in a way that reuses them in edges -- in other
        words, when edges are loaded they use their corresponding task IDs to access the
        correct Task objects out of a cache.
        """

        class ArgTask(Task):
            def run(self, x):
                return x

        f = Flow()
        t1, t2, t3 = Task("a"), Task("b"), ArgTask("c")

        f.add_edge(t1, t2)
        f.add_edge(t2, t3, key="x")
        f.add_edge(t1, t3, mapped=True)

        serialized = core.FlowSchema().dump(f)
        deserialized = core.FlowSchema().load(serialized)

        d1, d2, d3 = sorted(deserialized.tasks, key=lambda t: t.name)
        assert deserialized.edges == {
            Edge(d1, d2),
            Edge(d2, d3, key="x"),
            Edge(d1, d3, mapped=True),
        }
