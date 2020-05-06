import json
import logging
import uuid
from datetime import timedelta
from typing import Any, Union

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.engine.cache_validators import all_inputs, duration_only, never_use
from prefect.engine.result_handlers import JSONResultHandler, ResultHandler
from prefect.engine.results import PrefectResult
from prefect.utilities.configuration import set_temporary_config
from prefect.utilities.tasks import task


class AddTask(Task):
    def run(self, x, y=1):
        return x + y


class TestCreateTask:
    """Test various Task constructors"""

    def test_create_task_with_no_args(self):
        """Tasks can be created with no arguments"""
        assert Task()

    def test_create_task_is_not_auto_generated(self):
        assert Task().auto_generated is False

    def test_create_task_with_name(self):
        t1 = Task()
        assert t1.name == "Task"

        t2 = Task(name="test")
        assert t2.name == "test"

    def test_create_task_with_cache_key(self):
        t1 = Task()
        assert t1.cache_key is None

        t2 = Task(cache_key="test")
        assert t2.cache_key == "test"

    def test_create_task_with_slug(self):
        t1 = Task()
        assert t1.slug
        assert uuid.UUID(t1.slug)  # slug is a UUID

        t2 = Task(slug="test")
        assert t2.slug == "test"

    def test_create_task_with_max_retries(self):
        t1 = Task()
        assert t1.max_retries == 0

        t2 = Task(max_retries=5, retry_delay=timedelta(0))
        assert t2.max_retries == 5

    def test_create_task_with_retry_delay(self):
        t2 = Task(retry_delay=timedelta(seconds=30), max_retries=1)
        assert t2.retry_delay == timedelta(seconds=30)

    def test_create_task_with_max_retries_and_no_retry_delay(self):
        with pytest.raises(ValueError):
            Task(max_retries=1, retry_delay=None)

    def test_create_task_with_retry_delay_and_no_max_retries(self):
        with pytest.raises(
            ValueError,
            match="A `max_retries` argument greater than 0 must be provided if specifying a retry delay",
        ):
            Task(retry_delay=timedelta(seconds=30))

    @pytest.mark.parametrize("max_retries", [None, 0, False])
    def test_create_task_with_retry_delay_and_invalid_max_retries(self, max_retries):
        with pytest.raises(
            ValueError,
            match="A `max_retries` argument greater than 0 must be provided if specifying a retry delay",
        ):
            Task(retry_delay=timedelta(seconds=30), max_retries=max_retries)

    def test_create_task_with_timeout(self):
        t1 = Task()
        assert t1.timeout == None

        with pytest.raises(TypeError):
            Task(timeout=0.5)

        t3 = Task(timeout=1)
        assert t3.timeout == 1

        with set_temporary_config({"tasks.defaults.timeout": 3}):
            t4 = Task()
            assert t4.timeout == 3

    def test_create_task_with_trigger(self):
        t1 = Task()
        assert t1.trigger is prefect.triggers.all_successful

        t2 = Task(trigger=prefect.triggers.all_failed)
        assert t2.trigger == prefect.triggers.all_failed

    def test_create_task_without_state_handler(self):
        assert Task().state_handlers == []

    @pytest.mark.parametrize("handlers", [[lambda *a: 1], [lambda *a: 1, lambda *a: 2]])
    def test_create_task_with_state_handler(self, handlers):
        assert Task(state_handlers=handlers).state_handlers == handlers

    def test_create_task_with_on_failure(self):
        t = Task(on_failure=lambda *args: None)
        assert len(t.state_handlers) == 1

    def test_create_task_illegal_handler(self):
        with pytest.raises(TypeError):
            Task(state_handlers=lambda *a: 1)

    def test_class_instantiation_rejects_varargs(self):
        with pytest.raises(ValueError):

            class VarArgsTask(Task):
                def run(self, x, *y):
                    pass

    def test_class_instantiation_rejects_mapped_kwarg(self):
        with pytest.raises(ValueError):

            class MappedTasks(Task):
                def run(self, x, mapped):
                    pass

        with pytest.raises(ValueError):

            class MappedTasks(Task):
                def run(self, x, mapped=None):
                    pass

    def test_class_instantiation_rejects_mapped_kwarg_decorator(self):
        with pytest.raises(ValueError):

            @task
            def run(x, mapped):
                pass

        with pytest.raises(ValueError):

            @task
            def run(x, mapped=None):
                pass

    def test_class_instantiation_rejects_upstream_tasks_kwarg(self):
        with pytest.raises(ValueError):

            class UpstreamTasks(Task):
                def run(self, x, upstream_tasks):
                    pass

        with pytest.raises(ValueError):

            class UpstreamTasks(Task):
                def run(self, x, upstream_tasks=None):
                    pass

    def test_class_instantiation_rejects_upstream_tasks_kwarg_decorator(self):
        with pytest.raises(ValueError):

            @task
            def run(x, upstream_tasks):
                pass

        with pytest.raises(ValueError):

            @task
            def run(x, upstream_tasks=None):
                pass

    def test_class_instantiation_rejects_flow_kwarg(self):
        with pytest.raises(ValueError):

            class FlowTasks(Task):
                def run(self, x, flow):
                    pass

        with pytest.raises(ValueError):

            class FlowTasks(Task):
                def run(self, x, flow=None):
                    pass

    def test_class_instantiation_rejects_flow_kwarg_decorator(self):
        with pytest.raises(ValueError):

            @task
            def run(x, flow):
                pass

        with pytest.raises(ValueError):

            @task
            def run(x, flow=None):
                pass

    def test_class_instantiation_rejects_task_args_kwarg(self):
        with pytest.raises(ValueError):

            class TaskArgs(Task):
                def run(self, x, task_args):
                    pass

        with pytest.raises(ValueError):

            class TaskArgs(Task):
                def run(self, x, task_args=None):
                    pass

    def test_class_instantiation_rejects_task_args_kwarg_decorator(self):
        with pytest.raises(ValueError):

            @task
            def run(x, task_args):
                pass

        with pytest.raises(ValueError):

            @task
            def run(x, task_args=None):
                pass

    def test_class_instantiation_raises_helpful_warning_for_unsupported_callables(self):
        with pytest.raises(ValueError, match="This function can not be inspected"):
            task(zip)

    def test_create_task_with_and_without_cache_for(self):
        t1 = Task()
        assert t1.cache_validator is never_use
        t2 = Task(cache_for=timedelta(days=1))
        assert t2.cache_validator is duration_only
        t3 = Task(cache_for=timedelta(days=1), cache_validator=all_inputs)
        assert t3.cache_validator is all_inputs

    def test_bad_cache_kwarg_combo(self):
        with pytest.warns(UserWarning, match=".*Task will not be cached.*"):
            Task(cache_validator=all_inputs)

    def test_create_task_with_result_handler_is_deprecated_and_converts_to_result(self):
        t1 = Task()
        assert not hasattr(t1, "result_handler")

        with pytest.warns(UserWarning, match="deprecated"):
            t2 = Task(result_handler=JSONResultHandler())

        assert not hasattr(t2, "result_handler")
        assert isinstance(t2.result, PrefectResult)

    def test_create_task_with_and_without_result(self):
        t1 = Task()
        assert t1.result is None
        t2 = Task(result=PrefectResult())
        assert isinstance(t2.result, PrefectResult)

    def test_create_parameter_uses_prefect_result(self):
        p = Parameter("p")
        assert isinstance(p.result, PrefectResult)

    def test_create_task_with_and_without_checkpoint(self):
        t = Task()
        assert t.checkpoint is None

        s = Task(checkpoint=True)
        assert s.checkpoint is True

    def test_create_task_with_and_without_log_stdout(self):
        t = Task()
        assert t.log_stdout is False

        s = Task(log_stdout=True)
        assert s.log_stdout is True


def test_task_has_logger():
    t = Task()
    assert isinstance(t.logger, logging.Logger)
    assert t.logger.name == "prefect.Task"


def test_task_has_logger_with_informative_name():
    t = Task(name="foo")
    assert isinstance(t.logger, logging.Logger)
    assert t.logger.name == "prefect.foo"


def test_task_produces_no_result():
    t = Task()
    assert t.run() is None


def test_task_is_not_iterable():
    t = Task()
    with pytest.raises(TypeError):
        list(t)


def test_tags_are_added_when_arguments_are_bound():
    t1 = AddTask(tags=["math"])
    t2 = AddTask(tags=["math"])

    with prefect.context(tags=["test"]):
        with Flow(name="test"):
            t1.bind(1, 2)
            t3 = t2(1, 2)

    assert t1.tags == {"math", "test"}
    assert t3.tags == {"math", "test"}


def test_tags():
    t1 = Task()
    assert t1.tags == set()

    with pytest.raises(TypeError):
        Task(tags="test")

    t3 = Task(tags=["test", "test2", "test"])
    assert t3.tags == {"test", "test2"}

    with prefect.context(tags=["test"]):
        t4 = Task()
        assert t4.tags == {"test"}

    with prefect.context(tags=["test1", "test2"]):
        t5 = Task(tags=["test3"])
        assert t5.tags == {"test1", "test2", "test3"}


class TestInputsOutputs:
    class add(Task):
        def run(self, x, y: int = 1) -> int:
            return x + y

    @task
    def mult(x, y: int = 1) -> int:
        return x * y

    def test_inputs(self):
        assert self.add().inputs() == dict(
            x=dict(type=Any, required=True, default=None),
            y=dict(type=int, required=False, default=1),
        )

    def test_inputs_task_decorator(self):
        with Flow("test"):
            assert self.mult(x=1).inputs() == dict(
                x=dict(type=Any, required=True, default=None),
                y=dict(type=int, required=False, default=1),
            )

    def test_outputs(self):
        assert self.add().outputs() == int

    def test_outputs_task_decorator(self):
        with Flow("test"):
            assert self.mult(x=1).outputs() == int


class TestTaskCopy:
    def test_copy_copies(self):
        class CopyTask(Task):
            class_attr = 42

            def __init__(self, instance_val, **kwargs):
                self.instance_val = instance_val
                super().__init__(**kwargs)

            def run(self, run_val):
                return (run_val, self.class_attr, self.instance_val)

        ct = CopyTask("username")
        other = ct.copy()
        assert isinstance(other, CopyTask)
        assert ct is not other
        assert hash(ct) != hash(other)
        assert ct != other
        assert other.run("pass") == ("pass", 42, "username")

    def test_copy_warns_if_dependencies_in_active_flow(self):
        t1 = Task()
        t2 = Task()

        with Flow(name="test"):
            t1.set_dependencies(downstream_tasks=[t2])
            with pytest.warns(UserWarning):
                t1.copy()

            with Flow(name="test"):
                # no dependencies in this flow
                t1.copy()

    def test_copy_changes_slug(self):
        t1 = Task(slug="test")
        t2 = t1.copy()
        assert t1.slug == "test"
        assert t1.slug != t2.slug

    def test_copy_accepts_task_args(self):
        t = Task()
        t2 = t.copy(name="new-task")
        t3 = t.copy(**{"max_retries": 4200})

        assert t2.name == "new-task"
        assert t3.max_retries == 4200

    def test_copy_accepts_slug_as_task_args(self):
        t = Task(slug="test")
        t2 = t.copy(slug="test-2")
        assert t.slug == "test"
        assert t2.slug == "test-2"


def test_task_has_slug():
    t1 = Task()
    t2 = Task()

    assert t1.slug and t1.slug != t2.slug


class TestDependencies:
    def test_set_downstream(self):
        f = Flow(name="test")
        t1 = Task()
        t2 = Task()
        t1.set_downstream(t2, flow=f)
        assert Edge(t1, t2) in f.edges

    def test_set_downstream_context(self):
        with Flow(name="test") as f:
            t1 = Task()
            t2 = Task()
            t1.set_downstream(t2)
            assert Edge(t1, t2) in f.edges

    def test_set_downstream_no_flow(self):
        f = Flow(name="test")
        t1 = Task()
        t2 = Task()
        with pytest.raises(ValueError, match="No Flow was passed"):
            t1.set_downstream(t2)

    @pytest.mark.parametrize(
        "props", [{"mapped": True}, {"key": "x"}, {"key": "x", "mapped": True}]
    )
    def test_set_downstream_with_properties(self, props):
        with Flow(name="test") as f:
            t1 = Task()
            t2 = Task()
            t1.set_downstream(t2, **props)
            assert Edge(t1, t2, **props) in f.edges

    def test_set_upstream(self):
        f = Flow(name="test")
        t1 = Task()
        t2 = Task()
        t2.set_upstream(t1, flow=f)
        assert Edge(t1, t2) in f.edges

    def test_set_upstream_context(self):
        with Flow(name="test") as f:
            t1 = Task()
            t2 = Task()
            t2.set_upstream(t1)
            assert Edge(t1, t2) in f.edges

    def test_set_upstream_no_flow(self):
        f = Flow(name="test")
        t1 = Task()
        t2 = Task()
        with pytest.raises(ValueError, match="No Flow was passed"):
            t2.set_upstream(t1)

    @pytest.mark.parametrize(
        "props", [{"mapped": True}, {"key": "x"}, {"key": "x", "mapped": True}]
    )
    def test_set_upstream_with_properties(self, props):
        with Flow(name="test") as f:
            t1 = Task()
            t2 = Task()
            t2.set_upstream(t1, **props)
            assert Edge(t1, t2, **props) in f.edges


class TestSerialization:
    def test_serialization(self):
        t = Task(name="test")
        s = t.serialize()

        assert isinstance(s, dict)
        assert s["slug"] == t.slug
        assert s["type"] == "prefect.core.task.Task"
        assert s["name"] == t.name

    def test_subclass_serialization(self):
        class NewTask(Task):
            pass

        s = NewTask().serialize()

        assert isinstance(s, dict)
        assert s["type"].endswith(".NewTask")

    def test_deserialization(self):
        t = Task(name="test")
        s = t.serialize()
        t2 = prefect.serialization.task.TaskSchema().load(s)
        assert isinstance(t2, Task)
        assert t2.name == t.name

    def test_subclass_deserialization(self):
        class NewTask(Task):
            pass

        t = NewTask(name="test")
        s = t.serialize()
        t2 = prefect.serialization.task.TaskSchema().load(s)
        assert type(t2) is Task
        assert not isinstance(t2, NewTask)
        assert t2.name == t.name

    def test_parameter_serialization(self):
        p = Parameter(name="p")
        serialized = p.serialize()
        assert serialized["name"] == "p"
        assert serialized["default"] is None
        assert serialized["required"] is True

    def test_parameter_deserialization(self):
        p = Parameter(name="p")
        serialized = p.serialize()
        p2 = prefect.serialization.task.ParameterSchema().load(serialized)
        assert isinstance(p2, Parameter)
        assert p2.name == p.name
        assert p2.required == p.required
        assert p2.default == p.default


class TestTaskArgs:
    def test_task_args_raises_for_non_attrs(self):
        t = Task()
        with Flow(name="test") as f:
            with pytest.raises(AttributeError, match="foo"):
                res = t(task_args={"foo": "bar"})

    @pytest.mark.parametrize(
        "attr,val",
        [
            ("name", "foo-bar"),
            ("slug", "foo-bar"),
            ("max_retries", 4200),
            ("retry_delay", timedelta(seconds=1)),
            ("timeout", 12),
            ("skip_on_upstream_skip", False),
            ("cache_for", timedelta(seconds=1)),
        ],
    )
    def test_task_args_sets_new_attrs(self, attr, val):
        t = Task()
        with Flow(name="test") as f:
            res = t(task_args={attr: val})

        assert getattr(f.tasks.pop(), attr) == val

    @pytest.mark.parametrize(
        "attr,val",
        [
            ("name", "foo-bar"),
            ("slug", "foo-bar"),
            ("max_retries", 4200),
            ("retry_delay", timedelta(seconds=1)),
            ("timeout", 12),
            ("skip_on_upstream_skip", False),
            ("cache_for", timedelta(seconds=1)),
        ],
    )
    def test_task_args_sets_new_attrs_on_mapped_tasks(self, attr, val):
        t = Task()
        with Flow(name="test") as f:
            res = t.map(upstream_tasks=[1, 2, 3, 4], task_args={attr: val})

        tasks = f.get_tasks(name="Task")
        assert all(getattr(tt, attr) == val for tt in tasks)

    def test_tags_are_appended_to_when_updating_with_task_args(self):
        t = AddTask(tags=["math"])

        with prefect.context(tags=["test"]):
            with Flow(name="test"):
                t2 = t(1, 2, task_args={"name": "test-tags", "tags": ["new-tag"]})

        assert t2.tags == {"math", "test", "new-tag"}

    def test_task_check_mapped_args_are_subscriptable_in_advance(self):
        t = Task()
        with pytest.raises(TypeError):
            with Flow(name="test") as f:
                res = t.map({1, 2, 3, 4})


@pytest.mark.skip("Result handlers not yet deprecated")
def test_cache_options_show_deprecation():
    with pytest.warns(
        UserWarning, match=r"all cache_\* options on a Task will be deprecated*"
    ):
        Task(cache_for=object())

    with pytest.warns(
        UserWarning, match=r"all cache_\* options on a Task will be deprecated*"
    ):
        Task(cache_validator=object())

    with pytest.warns(
        UserWarning, match=r"all cache_\* options on a Task will be deprecated*"
    ):
        Task(cache_key=object())
