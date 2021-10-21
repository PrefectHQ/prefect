import pytest

from prefect.core import Edge, Flow, Parameter, Task
from prefect.tasks.core import collections
from prefect.tasks.core.constants import Constant
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
        with Flow(name="test") as flow:
            t = Task()
            t.set_dependencies(upstream_tasks=[4])
        assert len(flow.tasks) == 2
        assert any(isinstance(t, Constant) for t in flow.tasks)


class TestFunctionTask:
    def test_function_task_requires_callable(self):
        with pytest.raises(TypeError):
            FunctionTask(fn=1)

    def test_function_task_takes_name_from_callable(self):
        def my_fn():
            pass

        f = FunctionTask(fn=my_fn)
        assert f.name == "my_fn"

    def test_function_task_takes_name_from_arg_if_provided(self):
        def my_fn():
            pass

        f = FunctionTask(fn=my_fn, name="test")
        assert f.name == "test"

    def test_function_task_docstring(self):
        def my_fn():
            """An example docstring."""
            pass

        # Original docstring available on class
        assert "FunctionTask" in FunctionTask.__doc__

        # Wrapped function is docstring on instance
        f = FunctionTask(fn=my_fn)
        assert f.__doc__ == my_fn.__doc__

        # Lambdas do not have a function docstring
        f = FunctionTask(fn=lambda x: x + 1)
        assert f.__doc__ is None

    def test_function_task_sets__wrapped__(self):
        def my_fn():
            """An example function"""
            pass

        t = FunctionTask(fn=my_fn)
        assert t.__wrapped__ == my_fn
        assert not hasattr(FunctionTask, "__wrapped__")

    def test_function_task_raises_attribute_error(self):
        def my_fn():
            """An example function"""
            pass

        t = FunctionTask(fn=my_fn)
        with pytest.raises(
            AttributeError,
            match="'FunctionTask' object has no attribute 'unknown_attribute'",
        ):
            t.unknown_attribute


class TestCollections:
    def test_list_returns_a_list(self):
        l = collections.List()
        with Flow(name="test") as f:
            l.bind(1, 2)
        assert f.run().result[l].result == [1, 2]

    def test_list_binds_varargs(self):
        t1 = Task()
        t2 = Task()
        l = collections.List()
        with Flow(name="test") as f:
            l.bind(t1, t2)

        assert set([t1, t2, l]) == f.tasks
        assert Edge(t1, l, key="arg_1") in f.edges
        assert Edge(t2, l, key="arg_2") in f.edges

    def test_tuple_returns_a_tuple(self):
        l = collections.Tuple()
        with Flow(name="test") as f:
            l.bind(1, 2)
        assert f.run().result[l].result == (1, 2)

    def test_tuple_binds_varargs(self):
        t1 = Task()
        t2 = Task()
        l = collections.Tuple()
        with Flow(name="test") as f:
            l.bind(t1, t2)

        assert set([t1, t2, l]) == f.tasks
        assert Edge(t1, l, key="arg_1") in f.edges
        assert Edge(t2, l, key="arg_2") in f.edges

    def test_set_returns_a_set(self):
        l = collections.Set()
        with Flow(name="test") as f:
            l.bind(1, 2)
        assert f.run().result[l].result == set([1, 2])

    def test_set_binds_varargs(self):
        t1 = Task()
        t2 = Task()
        l = collections.Set()
        with Flow(name="test") as f:
            l.bind(t1, t2)

        assert set([t1, t2, l]) == f.tasks
        assert Edge(t1, l, key="arg_1") in f.edges
        assert Edge(t2, l, key="arg_2") in f.edges

    def test_dict_returns_a_dict(self):
        l = collections.Dict()
        with Flow(name="test") as f:
            l.bind(keys=["a", "b"], values=[1, 2])
        assert f.run().result[l].result == dict(a=1, b=2)

    def test_dict_handles_non_string_keys(self):
        l = collections.Dict()
        with Flow(name="test") as f:
            l.bind(keys=[None, 55], values=[1, 2])
        assert f.run().result[l].result == {None: 1, 55: 2}

    def test_dict_raises_for_differing_length_key_value_pairs(self):
        l = collections.Dict()
        with Flow(name="test") as f:
            l.bind(keys=["a"], values=[1, 2])
        state = f.run()
        assert state.result[l].is_failed()
        assert isinstance(state.result[l].result, ValueError)

    def test_list_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow(name="test") as f:
            identity.bind(x=[x, y])
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.List) for t in f.tasks) == 1
        assert state.result[identity].result == [1, 2]

    def test_list_automatically_applied_to_callargs_imperative(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        f = Flow(name="test")
        f.add_task(identity)
        identity.bind(x=[x, y], flow=f)
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.List) for t in f.tasks) == 1
        assert state.result[identity].result == [1, 2]

    def test_tuple_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow(name="test") as f:
            identity.bind(x=(x, y))
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Tuple) for t in f.tasks) == 1
        assert state.result[identity].result == (1, 2)

    def test_tuple_automatically_applied_to_callargs_imperative(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        f = Flow(name="test")
        f.add_task(identity)
        identity.bind(x=(x, y), flow=f)
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Tuple) for t in f.tasks) == 1
        assert state.result[identity].result == (1, 2)

    def test_set_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow(name="test") as f:
            identity.bind(x=set([x, y]))
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Set) for t in f.tasks) == 1
        assert state.result[identity].result == set([1, 2])

    def test_set_automatically_applied_to_callargs_imperative(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        f = Flow(name="test")
        f.add_task(identity)
        identity.bind(x=set([x, y]), flow=f)
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 4
        assert sum(isinstance(t, collections.Set) for t in f.tasks) == 1
        assert state.result[identity].result == set([1, 2])

    def test_dict_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow(name="test") as f:
            identity.bind(x=dict(a=x, b=y))
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 5  # 2 params, identity, Dict, List of dict values
        assert sum(isinstance(t, collections.Dict) for t in f.tasks) == 1
        assert state.result[identity].result == dict(a=1, b=2)

    def test_dict_automatically_applied_to_callargs_imperative(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        f = Flow(name="test")
        f.add_task(identity)
        identity.bind(x=dict(a=x, b=y), flow=f)
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 5  # 2 params, identity, Dict, List of dict values
        assert sum(isinstance(t, collections.Dict) for t in f.tasks) == 1
        assert state.result[identity].result == dict(a=1, b=2)

    def test_nested_collection_automatically_applied_to_callargs(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        with Flow(name="test") as f:
            identity.bind(x=dict(a=[x, dict(y=y)], b=(y, set([x]))))
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 10
        assert state.result[identity].result == dict(a=[1, dict(y=2)], b=(2, set([1])))

    def test_nested_collection_automatically_applied_to_callargs_imperative(self):
        x = Parameter("x")
        y = Parameter("y")
        identity = IdentityTask()
        f = Flow(name="test")
        f.add_task(identity)
        identity.bind(x=dict(a=[x, dict(y=y)], b=(y, set([x]))), flow=f)
        state = f.run(parameters=dict(x=1, y=2))

        assert len(f.tasks) == 10
        assert state.result[identity].result == dict(a=[1, dict(y=2)], b=(2, set([1])))

    def test_list_maintains_sort_order_for_more_than_10_items(self):
        # https://github.com/PrefectHQ/prefect/issues/2451
        l = collections.List()
        with Flow(name="test") as f:
            l.bind(*list(range(15)))
        assert f.run().result[l].result == list(range(15))

    def test_tuple_maintains_sort_order_for_more_than_10_items(self):
        # https://github.com/PrefectHQ/prefect/issues/2451
        t = collections.Tuple()
        with Flow(name="test") as f:
            t.bind(*list(range(15)))
        assert f.run().result[t].result == tuple(range(15))
