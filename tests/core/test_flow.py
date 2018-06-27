import datetime

import pytest

import prefect
from prefect.core.flow import Flow
from prefect.core.task import Parameter, Task
from prefect.signals import PrefectError
from prefect.tasks.core.function_task import FunctionTask
from prefect.utilities.tasks import task


class AddTask(Task):
    def run(self, x, y):
        return x + y


@pytest.fixture
def add_flow():
    with Flow() as f:
        x = Parameter("x")
        y = Parameter("y", default=10)
        z = AddTask()
        f.set_dependencies(z, keyword_results=dict(x=x, y=y))
    return f


class TestCreateFlow:
    """ Test various Flow constructors """

    def test_create_flow_with_no_args(self):
        # name is not required
        assert Flow()

    def test_create_flow_with_name(self):
        f1 = Flow()
        assert f1.name is "Flow"

        f2 = Flow(name="test")
        assert f2.name == "test"

    def test_create_flow_with_version(self):
        f1 = Flow()
        assert f1.version is None

        f2 = Flow(version="test")
        assert f2.version == "test"

    def test_create_flow_with_description(self):
        f1 = Flow()
        assert f1.description is None

        f2 = Flow(description="test")
        assert f2.description == "test"

    def test_create_flow_with_schedule(self):
        f1 = Flow()
        assert isinstance(f1.schedule, prefect.schedules.NoSchedule)

        cron = prefect.schedules.CronSchedule("* * * * *")
        f2 = Flow(schedule=cron)
        assert f2.schedule == cron


def test_add_task():
    f = Flow()
    t = Task()
    f.add_task(t)
    assert t in f.tasks


def test_add_task_wrong_type():
    f = Flow()

    with pytest.raises(TypeError):
        f.add_task(1)


def test_ok_to_add_a_task_twice():
    f = Flow()
    t = Task()
    f.add_task(t)
    f.add_task(t)


def test_context_manager():
    with Flow() as f1:
        with Flow() as f2:
            t2 = Task()
        t1 = Task()

    assert t1 in f1.tasks
    assert t2 in f2.tasks
    assert t2 not in f1.tasks
    assert t1 not in f2.tasks


def test_that_flow_adds_and_removes_itself_from_prefect_context():
    assert "_flow" not in prefect.context
    with Flow() as f1:
        assert prefect.context._flow is f1
        with Flow() as f2:
            assert prefect.context._flow is f2
        assert prefect.context._flow is f1
    assert "_flow" not in prefect.context


def test_edge():
    f = Flow()
    t1 = Task()
    t2 = Task()
    f.add_edge(upstream_task=t1, downstream_task=t2)
    assert f.upstream_tasks(t2) == set([t1])
    assert f.upstream_tasks(t1) == set()
    assert f.downstream_tasks(t2) == set()
    assert f.downstream_tasks(t1) == set([t2])
    assert f.edges_to(t2) == f.edges_from(t1)


def test_iter():
    """
    Tests that iterating over a Flow yields the tasks in order
    """
    with Flow("test") as f:
        t1 = Task()
        t2 = Task()
        f.add_edge(upstream_task=t2, downstream_task=t1)
    assert tuple(f) == f.sorted_tasks() == (t2, t1)


def test_detect_cycle():
    f = Flow()
    t1 = Task()
    t2 = Task()
    t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)
    with pytest.raises(ValueError):
        f.add_edge(t3, t1)


def test_root_tasks():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    assert f.root_tasks() == set([t1])


def test_terminal_tasks():
    with Flow() as f:
        t1 = Task()
        t2 = Task()
        t3 = Task()

    f.add_edge(t1, t2)
    f.add_edge(t2, t3)

    assert f.terminal_tasks() == set([t3])


def test_merge():
    f1 = Flow()
    f2 = Flow()

    t1 = Task()
    t2 = Task()
    t3 = Task()

    f1.add_edge(t1, t2)
    f2.add_edge(t2, t3)

    f2.update(f1)
    assert f2.tasks == set([t1, t2, t3])
    assert len(f2.edges) == 2
