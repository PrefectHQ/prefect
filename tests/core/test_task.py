import json
from datetime import timedelta

import pytest

import prefect
from prefect.core import Flow, Parameter, Task
from prefect.engine.cache_validators import all_inputs, duration_only, never_use
from prefect.utilities.tasks import task


class AddTask(Task):
    def run(self, x, y=1):
        return x + y


@pytest.fixture
def copyclass():
    class CopyTask(Task):
        class_attr = 42

        def __init__(self, instance_val, **kwargs):
            self.instance_val = instance_val
            super().__init__(**kwargs)

        def run(self, run_val):
            return (run_val, self.class_attr, self.instance_val)

    return CopyTask


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

        t2 = Task(max_retries=5)
        assert t2.max_retries == 5

    def test_create_task_with_retry_delay(self):
        t1 = Task()
        assert t1.retry_delay == timedelta(minutes=1)

        t2 = Task(retry_delay=timedelta(seconds=30))
        assert t2.retry_delay == timedelta(seconds=30)

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

    def test_class_instantiation_rejects_varargs(self):
        with pytest.raises(ValueError):

            class VarArgsTask(Task):
                def run(self, x, *y):
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


def test_groups():
    t1 = Task()
    assert t1.group == ""

    t2 = Task(group="test")
    assert t2.group == "test"

    with prefect.context(_group="test"):
        t3 = Task()
        assert t3.group == "test"


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
        assert t5.tags == set(["test3"])


def test_inputs():
    """ Test inferring input names """
    assert AddTask().inputs() == ("x", "y")


def test_copy_copies(copyclass):
    ct = copyclass("username")
    other = ct.copy()
    assert isinstance(other, copyclass)
    assert ct is not other
    assert hash(ct) != hash(other)
    assert ct != other
    assert other.run("pass") == ("pass", 42, "username")
