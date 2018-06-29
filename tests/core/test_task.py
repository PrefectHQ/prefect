import json
from datetime import timedelta

import pytest

import prefect
from prefect.core import Flow, Parameter, Task
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

    def test_create_task_with_checkpoint(self):
        t1 = Task()
        assert not t1.checkpoint

        t2 = Task(checkpoint=True)
        assert t2.checkpoint

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

    t2 = Task(tags="test")
    assert t2.tags == set(["test"])

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
