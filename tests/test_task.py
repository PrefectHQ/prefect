import json
import pytest

import prefect
from prefect.flow import Flow, TaskResult
from prefect.task import Task, Parameter
from prefect.utilities.tasks import task


class AddTask(Task):
    def run(self, x, y=1):
        return x + y


def test_create_task():
    t1 = Task()
    t2 = Task()

    assert t1.id != t2.id
    assert t1.name == t2.name


def test_task_inputs():
    """Test inferring the names of task inputs from the run fn signature"""

    t = AddTask()
    assert t.inputs() == ("x", "y")


def test_create_task_in_context():
    t1 = Task()
    with Flow() as f:
        t2 = Task()

    assert t1 not in f.tasks
    assert t2 in f.tasks


def test_call_task():
    t1 = Task()
    t2 = Task()
    add = AddTask()

    # combining three tasks creates a flow
    with Flow():
        result_1 = add(t1, t2)
    assert isinstance(result_1, TaskResult)
    assert result_1.flow.tasks == set([t1, t2, add])


def test_task_factory_decorator():
    @task()
    def add(x, y=1):
        return x + y

    assert isinstance(add(1, 2), TaskResult)


def test_serialize():
    t = Task()
    serialized = t.serialize()
    assert t.id == serialized["id"]
    assert t.name == serialized["name"]
    assert t.description == serialized["description"]
    assert t.max_retries == serialized["max_retries"]
    assert t.retry_delay == serialized["retry_delay"]
    assert t.timeout == serialized["timeout"]
    assert t.trigger == serialized["trigger"]


def test_json():
    t = Task()
    assert t.serialize() == json.loads(json.dumps(t))


def test_deserialize():
    t1 = Task()
    t2 = Task.deserialize(t1.serialize())
    assert t2 == t1
    assert t2.id == t1.id
    assert t2.name == t1.name
    assert prefect.base.get_object_by_id(t1.id) is t2


def test_deserialize_parameter():
    p = Parameter("x", default=1)
    assert isinstance(Task.deserialize(p.serialize()), Parameter)
