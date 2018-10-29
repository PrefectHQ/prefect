import json
import logging
from datetime import timedelta

import pytest

import prefect
from prefect.core import Edge, Flow, Parameter, Task
from prefect.engine.cache_validators import all_inputs, duration_only, never_use
from prefect.utilities.tasks import task


class AddTask(Task):
    def run(self, x, y=1):
        return x + y


class TestCreateTask:
    """Test various Task constructors"""

    def test_create_task_with_no_args(self):
        """Tasks can be created with no arguments"""
        assert Task()

    def test_create_task_with_name(self):
        t1 = Task()
        assert t1.name == "Task"

        t2 = Task(name="test")
        assert t2.name == "test"

    def test_create_task_with_slug(self):
        t1 = Task()
        assert t1.slug is None

        t2 = Task(slug="test")
        assert t2.slug == "test"

    def test_create_task_with_description(self):
        t1 = Task()
        assert t1.description is None

        t2 = Task(description="test")
        assert t2.description == "test"

    def test_create_task_with_max_retries(self):
        t1 = Task()
        assert t1.max_retries == 0

        t2 = Task(max_retries=5, retry_delay=timedelta(0))
        assert t2.max_retries == 5

    def test_create_task_with_retry_delay(self):
        t2 = Task(retry_delay=timedelta(seconds=30))
        assert t2.retry_delay == timedelta(seconds=30)

    def test_create_task_with_max_retries_and_no_retry_delay(self):
        with pytest.raises(ValueError):
            Task(max_retries=1, retry_delay=None)

    def test_create_task_with_timeout(self):
        t1 = Task()
        assert t1.timeout is None

        t2 = Task(timeout=timedelta(seconds=30))
        assert t2.timeout == timedelta(seconds=30)

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

    def test_class_instantiation_rejects_upstream_tasks_kwarg(self):
        with pytest.raises(ValueError):

            class UpstreamTasks(Task):
                def run(self, x, upstream_tasks):
                    pass

        with pytest.raises(ValueError):

            class UpstreamTasks(Task):
                def run(self, x, upstream_tasks=None):
                    pass

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


def test_task_has_logger():
    t = Task()
    assert isinstance(t.logger, logging.Logger)
    assert t.logger.name == "prefect.Task"


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

    with prefect.context(_tags=["test"]):
        with Flow():
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
    assert t3.tags == set(["test", "test2"])

    with prefect.context(_tags=["test"]):
        t4 = Task()
        assert t4.tags == set(["test"])

    with prefect.context(_tags=["test1", "test2"]):
        t5 = Task(tags=["test3"])
        assert t5.tags == set(["test1", "test2", "test3"])


def test_inputs():
    """ Test inferring input names """
    assert AddTask().inputs() == ("x", "y")


def test_copy_copies():
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


def test_copy_warns_if_dependencies_in_active_flow():
    t1 = Task()
    t2 = Task()

    with Flow():
        t1.set_dependencies(downstream_tasks=[t2])
        with pytest.warns(UserWarning):
            t1.copy()

        with Flow():
            # no dependencies in this flow
            t1.copy()


class TestDependencies:
    """
    Most dependnecy tests are done in test_flow.py.
    """

    def test_set_downstream(self):
        with Flow() as f:
            t1 = Task()
            t2 = Task()
            t1.set_downstream(t2)
            assert Edge(t1, t2) in f.edges

    def test_set_upstream(self):
        with Flow() as f:
            t1 = Task()
            t2 = Task()
            t2.set_upstream(t1)
            assert Edge(t1, t2) in f.edges
