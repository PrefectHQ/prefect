import inspect
import logging
from datetime import timedelta
from typing import Any, Tuple

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.engine.cache_validators import all_inputs, duration_only, never_use
from prefect.engine.results import PrefectResult, LocalResult
from prefect.utilities.configuration import set_temporary_config
from prefect.configuration import process_task_defaults
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
        assert t1.slug is None

        t2 = Task(slug="test")
        assert t2.slug == "test"

    def test_create_task_with_max_retries(self):
        t1 = Task()
        assert t1.max_retries == 0

        t2 = Task(max_retries=5, retry_delay=timedelta(0))
        assert t2.max_retries == 5

        with set_temporary_config({"tasks.defaults.max_retries": 3}) as config:
            # Cover type casting of task defaults
            process_task_defaults(config)
            t3 = Task(retry_delay=timedelta(0))
            assert t3.max_retries == 3

    def test_create_task_with_retry_delay(self):
        t1 = Task(retry_delay=timedelta(seconds=30), max_retries=1)
        assert t1.retry_delay == timedelta(seconds=30)

        with set_temporary_config({"tasks.defaults.retry_delay": 3}) as config:
            # Cover type casting of task defaults
            process_task_defaults(config)
            t2 = Task(max_retries=1)
            assert t2.retry_delay == timedelta(seconds=3)

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

    def test_create_task_with_max_retry_override_to_0(self):
        with set_temporary_config(
            {"tasks.defaults.max_retries": 3, "tasks.defaults.retry_delay": 3}
        ) as config:
            process_task_defaults(config)
            t = Task(max_retries=0, retry_delay=None)
            assert t.max_retries == 0
            assert t.retry_delay is None

            # max_retries set to 0 will not pull retry_delay from the config
            process_task_defaults(config)
            t = Task(max_retries=0)
            assert t.max_retries == 0
            assert t.retry_delay is None

    def test_create_task_with_timeout(self):
        t1 = Task()
        assert t1.timeout is None

        with pytest.raises(TypeError):
            Task(timeout=0.5)

        t3 = Task(timeout=1)
        assert t3.timeout == 1

        with set_temporary_config({"tasks.defaults.timeout": 3}) as config:
            # Cover type casting of task defaults
            process_task_defaults(config)
            t4 = Task()
            assert t4.timeout == 3

        t4 = Task(timeout=timedelta(seconds=2))
        assert t4.timeout == 2

        with pytest.warns(UserWarning):
            t5 = Task(timeout=timedelta(seconds=3, milliseconds=1, microseconds=1))
        assert t5.timeout == 3

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

    def test_create_task_with_retry_on(self):
        t1 = Task()
        assert t1.retry_on is None

        with pytest.raises(ValueError, match=" `max_retries` must be provided"):
            Task(retry_on={RuntimeError})

        with pytest.raises(
            TypeError, match="exception type but got an instance of str"
        ):
            Task(retry_on={"foo"}, max_retries=2, retry_delay=timedelta(seconds=1))

        t2 = Task(
            retry_on={RuntimeError, ValueError},
            max_retries=2,
            retry_delay=timedelta(seconds=1),
        )
        assert t2.retry_on == {RuntimeError, ValueError}

        t3 = Task(
            retry_on=IOError,
            max_retries=2,
            retry_delay=timedelta(seconds=1),
        )
        assert t3.retry_on == {IOError}

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

    def test_task_signature_generation(self):
        class Test(Task):
            def run(self, x: int, y: bool, z: int = 1, **kwargs):
                pass

        t = Test()

        sig = inspect.signature(t)
        # signature is a superset of the `run` method
        for k, p in inspect.signature(t.run).parameters.items():
            assert sig.parameters[k] == p
        # extra kwonly args to __call__ also in sig
        assert set(sig.parameters).issuperset(
            {"mapped", "task_args", "upstream_tasks", "flow"}
        )
        assert sig.return_annotation == "Task"

        # doesn't override class signature
        class_sig = inspect.signature(Test)
        assert "name" in class_sig.parameters

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

    def test_create_task_with_task_run_name(self):
        t1 = Task()
        assert t1.task_run_name is None

        t2 = Task(task_run_name="test")
        assert t2.task_run_name == "test"

        t2 = Task(task_run_name=lambda: 42)
        assert t2.task_run_name() == 42


def test_task_has_logger():
    t = Task()
    assert isinstance(t.logger, logging.Logger)


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

        with Flow(name="test") as flow:
            t1.set_dependencies(downstream_tasks=[t2])
            with pytest.warns(UserWarning, match="You are making a copy"):
                flow.add_task(t1.copy())

        with Flow(name="test") as flow:
            with pytest.warns(None) as rec:
                flow.add_task(t1.copy())
            # no dependencies in this flow
            assert len(rec) == 0

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

    def test_copy_appropriately_sets_result_target_if_target_provided(self):
        # https://github.com/PrefectHQ/prefect/issues/2588
        @task(target="target", result=LocalResult(dir="."))
        def X():
            pass

        @task
        def Y():
            pass

        with Flow("test"):
            x = X()
            y = Y(task_args=dict(target="target", result=LocalResult(dir=".")))

        assert x.result.location == "target"
        assert y.result.location == "target"


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

    def test_set_dependencies_stream_allows_chaining(self):
        t1 = Task()
        t2 = Task()
        t3 = Task()
        with Flow(name="test") as f:
            t1_result = t1()
            t2_result = t2()
            t3_result = t3()

            assert t1_result.set_downstream(t2_result) is t1_result
            assert t3_result.set_upstream(t2_result) is t3_result
            assert (
                t3_result.set_dependencies(f, upstream_tasks=[t1_result]) is t3_result
            )


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
        with Flow(name="test"):
            with pytest.raises(AttributeError, match="foo"):
                t(task_args={"foo": "bar"})

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
            t(task_args={attr: val})

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
            t.map(upstream_tasks=[1, 2, 3, 4], task_args={attr: val})

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
            with Flow(name="test"):
                t.map({1, 2, 3, 4})


class TestTaskNout:
    def test_nout_defaults_to_none(self):
        @task
        def test(self):
            pass

        assert test.nout is None

    def test_nout_provided_explicitly(self):
        @task(nout=2)
        def test(self):
            pass

        assert test.nout == 2

    @pytest.mark.parametrize(
        "ret_type, nout",
        [
            (int, None),
            (Tuple, None),
            (Tuple[()], 0),
            (Tuple[int, ...], None),
            (Tuple[int, int], 2),
            (Tuple[int, float, str], 3),
        ],
    )
    def test_nout_inferred_from_signature(self, ret_type, nout):
        @task
        def test(a) -> ret_type:
            pass

        assert test.nout == nout

    def test_nout_none_not_iterable(self):
        @task
        def test(a):
            return a + 1, a - 1

        with Flow("test"):
            with pytest.raises(TypeError, match="Task is not iterable"):
                a, b = test(1)

    def test_nout_provided_is_iterable(self):
        @task(nout=2)
        def test(a):
            return a + 1, a - 1

        with Flow("test") as flow:
            a, b = test(1)
        res = flow.run()
        assert res.result[a].result == 2
        assert res.result[b].result == 0

    def test_nout_not_set_on_mapped_tasks(self):
        @task(nout=2)
        def test(a):
            return a + 1, a - 1

        with Flow("test"):
            with pytest.raises(TypeError, match="Task is not iterable"):
                a, b = test.map(range(10))


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


def test_passing_task_to_task_constructor_raises_helpful_warning():
    class MyTask(Task):
        def __init__(self, a, b, **kwargs):
            self.a = a
            self.b = b
            super().__init__(**kwargs)

    with Flow("test"):
        a = Task()()
        with pytest.warns(
            UserWarning, match="A Task was passed as an argument to MyTask"
        ):
            t = MyTask(1, a)()
        # Warning doesn't stop normal operation
        assert t.a == 1
        assert t.b == a


def test_task_init_uses_reserved_attribute_raises_helpful_warning():
    class MyTask(Task):
        def __init__(self, **kwargs):
            self.a = 1
            self.target = "oh no!"
            super().__init__(**kwargs)

    with Flow("test"):
        with pytest.warns(UserWarning, match="`MyTask` sets a `target` attribute"):
            MyTask()


@pytest.mark.parametrize("use_function_task", [True, False])
def test_task_called_outside_flow_context_raises_helpful_error(use_function_task):

    if use_function_task:

        @prefect.task
        def fn(x):
            return x

    else:

        class Fn(Task):
            def run(self, x):
                return x

        fn = Fn()

    with pytest.raises(
        ValueError,
        match=f"Could not infer an active Flow context while creating edge to {fn}",
    ) as exc_info:
        fn(1)

    run_call = "`fn.run(...)`" if use_function_task else "`Fn(...).run(...)`"
    assert (
        "If you're trying to run this task outside of a Flow context, "
        f"you need to call {run_call}" in str(exc_info)
    )


def test_result_pipe():
    t = prefect.task(lambda x, foo: x + 1)

    with prefect.Flow("test"):
        # A task created using .pipe should be identical to one created by using __call__
        assert vars(t(1, foo="bar")) == vars(t.pipe(t, foo="bar"))


def test_task_call_with_self_succeeds():
    import dataclasses

    @dataclasses.dataclass
    class TestClass:
        count: int

        def increment(self):
            self.count = self.count + 1

    seconds_task = task(
        TestClass.increment, target="{{task_slug}}_{{map_index}}", result=LocalResult()
    )
    initial = TestClass(count=0)

    with Flow("test") as flow:
        seconds_task(initial)
    assert flow.run().is_successful()
