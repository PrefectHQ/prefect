import pytest

from prefect.core import Flow, Task, Edge, Parameter
from prefect.tasks.core.constants import Constant
from prefect.tasks.core import collections
from prefect.tasks.core.function import FunctionTask


class IdentityTask(Task):
    def run(self, x):
        return x


class TestConstant:
    def test_constant_task_returns_its_value(self):
        x = Constant("x")
        assert x.run() == "x"

        y = Constant(100)
        assert y.run() == 100

    def test_automatic_create_constant_task(self):
        with Flow() as flow:
            t = Task()
            t.set_dependencies(upstream_tasks=[4])
        assert len(flow.tasks) == 2
        assert any(isinstance(t, Constant) for t in flow.tasks)


class TestCollections:
    def test_list_returns_a_list(self):
        l = collections.List()
        with Flow() as f:
            l.bind(1, 2)
        assert f.run(return_tasks=[l]).result[l].result == [1, 2]

    def test_list_binds_varargs(self):
        t1 = Task()
        t2 = Task()
        l = collections.List()
        with Flow() as f:
            l.bind(t1, t2)

        assert set([t1, t2, l]) == f.tasks
        assert Edge(t1, l, key="arg_1") in f.edges
        assert Edge(t2, l, key="arg_2") in f.edges

    def test_tuple_returns_a_tuple(self):
        l = collections.Tuple()
        with Flow() as f:
            l.bind(1, 2)
        assert f.run(return_tasks=[l]).result[l].result == (1, 2)

    def test_tuple_binds_varargs(self):
        t1 = Task()
        t2 = Task()
        l = collections.Tuple()
        with Flow() as f:
            l.bind(t1, t2)

        assert set([t1, t2, l]) == f.tasks
        assert Edge(t1, l, key="arg_1") in f.edges
        assert Edge(t2, l, key="arg_2") in f.edges

    def test_set_returns_a_set(self):
        l = collections.Set()
        with Flow() as f:
            l.bind(1, 2)
        assert f.run(return_tasks=[l]).result[l].result == set([1, 2])

    def test_set_binds_varargs(self):
        t1 = Task()
        t2 = Task()
        l = collections.Set()
        with Flow() as f:
            l.bind(t1, t2)

        assert set([t1, t2, l]) == f.tasks
        assert Edge(t1, l, key="arg_1") in f.edges
        assert Edge(t2, l, key="arg_2") in f.edges

    def test_dict_returns_a_dict(self):
        l = collections.Dict()
        with Flow() as f:
            l.bind(a=1, b=2)
        assert f.run(return_tasks=[l]).result[l].result == dict(a=1, b=2)

    def test_list_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow() as f:
            identity.bind(x=[x, y])
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[identity])

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.List) for t in f.tasks) == 1
        assert state.result[identity].result == [1, 2]

    def test_tuple_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow() as f:
            identity.bind(x=(x, y))
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[identity])

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Tuple) for t in f.tasks) == 1
        assert state.result[identity].result == (1, 2)

    def test_set_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow() as f:
            identity.bind(x=set([x, y]))
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[identity])

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Set) for t in f.tasks) == 1
        assert state.result[identity].result == set([1, 2])

    def test_dict_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow() as f:
            identity.bind(x=dict(a=x, b=y))
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[identity])

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Dict) for t in f.tasks) == 1
        assert state.result[identity].result == dict(a=1, b=2)

    def test_nested_collection_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow() as f:
            identity.bind(x=dict(a=[x, dict(y=y)], b=(y, set([x]))))
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[identity])

        assert len(f.tasks) == 8
        assert state.result[identity].result == dict(a=[1, dict(y=2)], b=(2, set([1])))
