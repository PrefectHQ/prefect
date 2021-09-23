import functools
import pytest

from prefect import Flow, Task, case, Parameter, resource_manager, task
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.state import Paused, Resume
from prefect.utilities import tasks, edges
from prefect.utilities.tasks import apply_map
from prefect.tasks.control_flow import merge
from prefect.tasks.core.constants import Constant


class TestTaskDecorator:
    def test_task_decorator_can_be_used_without_calling(self):
        @tasks.task
        def fun(x, y):
            return x + y

    def test_task_decorator_generates_new_tasks_upon_subsequent_calls(self):
        @tasks.task
        def fun(x, y):
            return x + y

        with Flow(name="test"):
            res1 = fun(1, 2)
            res2 = fun(1, 2)
        assert isinstance(res1, Task)
        assert isinstance(res2, Task)
        assert res1 is not res2

    def test_task_decorator_with_args_must_be_called_in_flow_context(self):
        @tasks.task
        def fn(x):
            return x

        with pytest.raises(
            ValueError,
            match=f"Could not infer an active Flow context while creating edge to {fn}",
        ):
            fn(1)

    def test_task_decorator_with_no_args_must_be_called_inside_flow_context(self):
        @tasks.task
        def fn():
            return 1

        with pytest.raises(ValueError):
            fn()

        with Flow(name="test"):
            assert isinstance(fn(), Task)

    def test_task_decorator_with_default_args_must_be_called_inside_flow_context(self):
        @tasks.task
        def fn(x=1):
            return x

        with pytest.raises(ValueError):
            fn()

        with Flow(name="test"):
            assert isinstance(fn(), Task)

    def test_task_decorator_with_required_args_must_be_called_with_args(self):
        @tasks.task
        def fn(x):
            return x

        with Flow(name="test"):
            with pytest.raises(TypeError):
                fn()

    def test_task_decorator_returns_task_instance(self):
        @tasks.task
        def fn(x):
            return x

        assert isinstance(fn, Task)

    def test_task_decorator_validates_run_signature_against_varargs(self):
        with pytest.raises(ValueError):

            @tasks.task
            def fn(*args):
                pass

    def test_task_decorator_validates_run_signature_against_upstream_tasks_kwarg(self):
        with pytest.raises(ValueError):

            @tasks.task
            def fn(upstream_tasks):
                pass

    def test_task_decorator_allows_for_decorator_chaining(self):
        def simple_dec(func):
            @functools.wraps(func)
            def wrapped(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapped

        @tasks.task
        @simple_dec
        def run(x):
            pass

        class A(Task):
            @simple_dec
            def run(self, x):
                pass

        @tasks.task
        @simple_dec
        @simple_dec
        def run(x):
            pass

        class A(Task):
            @simple_dec
            @simple_dec
            def run(self, x):
                pass

    def test_task_decorator_rejects_varargs_with_chained_decorator(self):
        def simple_dec(func):
            @functools.wraps(func)
            def wrapped(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapped

        with pytest.raises(ValueError):

            @tasks.task
            @simple_dec
            def run(self, x, *y):
                pass

        with pytest.raises(ValueError):

            @tasks.task
            @simple_dec
            @simple_dec
            def run(self, x, *y):
                pass


@tasks.task
def add(x, y):
    return x + y


@tasks.task
def inc(x):
    return x + 1


@tasks.task
def is_even(x):
    return x % 2 == 0


@tasks.task
def ranged(n):
    return range(n)


class TestApplyMap:
    def test_raises_no_flow_found(self):
        with pytest.raises(ValueError, match="flow in the current context"):
            apply_map(lambda x: inc(x), range(10))

    def test_raises_non_sequence_args(self):
        with Flow("test"):
            with pytest.raises(TypeError, match="non-sequence object"):
                apply_map(lambda x: inc(x), 1)

            with pytest.raises(TypeError, match="non-sequence object"):
                apply_map(lambda x: inc(x), x=1)

    @pytest.mark.parametrize("method", ["map", "set_dependencies", "add_edge"])
    def test_raises_use_map_in_mapped_function(self, method):
        if method == "map":

            def func(x):
                inc.map(x)

            pass_flow = False
        elif method == "set_dependencies":

            def func(x, flow):
                flow.add_task(inc)
                flow.set_dependencies(inc, keyword_tasks={"x": x}, mapped=True)

            pass_flow = True
        elif method == "add_edge":

            def func(x, flow):
                flow.add_task(inc)
                flow.add_edge(x, inc, key="x", mapped=True)

            pass_flow = True

        flow = Flow("test")
        with pytest.raises(ValueError, match="running from inside a mapped context"):
            if pass_flow:
                apply_map(func, range(3), flow=flow)
            else:
                with flow:
                    apply_map(func, range(3))

    def test_imperative_args_are_added_to_flow_before_mapping(self):
        # Check an edge case when mapping over tasks that haven't been added to flow yet.
        @tasks.task
        def data():
            return range(3)

        def func(a, flow):
            return inc.copy().bind(a, flow=flow)

        flow = Flow("test")
        res = apply_map(func, data, flow=flow)
        state = flow.run()
        assert state.result[res].result == [1, 2, 3]

    @pytest.mark.parametrize("api", ["functional", "imperative"])
    def test_apply_map_simple(self, api):
        if api == "functional":

            def func(x, y, z):
                a = add(x, y)
                a.name = "add-a"
                b = add(a, z)
                b.name = "add-b"
                c = add(b, 1)
                c.name = "add-c"
                return inc(c)

            with Flow("test") as flow:
                y = ranged(3)
                z = edges.unmapped(1)
                res = apply_map(func, range(3, 6), y=y, z=z)
        else:

            def func(x, y, z, flow):
                a = add.copy(name="add-a").bind(x, y, flow=flow)
                b = add.copy(name="add-b").bind(a, z, flow=flow)
                c = add.copy(name="add-c").bind(b, 1, flow=flow)
                return inc.copy().bind(c, flow=flow)

            flow = Flow("test")
            y = ranged.copy().bind(3, flow=flow)
            z = edges.unmapped(tasks.as_task(1, flow=flow))
            res = apply_map(func, range(3, 6), y=y, z=z, flow=flow)

        consts = {t.name: c for t, c in flow.constants.items()}
        assert consts == {"ranged": {"n": 3}, "add-b": {"y": 1}, "add-c": {"y": 1}}

        for task in flow.tasks:
            if task.name != "ranged":
                for e in flow.edges_to(task):
                    assert e.mapped

        state = flow.run()
        assert state.result[res].result == [6, 8, 10]

    def test_apply_map_return_multiple(self):
        def func(x, y):
            return inc(x), inc(y)

        with Flow("test") as flow:
            a, b = apply_map(func, range(3), range(3, 6))

        state = flow.run()
        assert state.result[a].result == [1, 2, 3]
        assert state.result[b].result == [4, 5, 6]

    def test_apply_map_disparate_length_args(self):
        def func(x, y):
            return inc(x), inc(y)

        with Flow("test") as flow:
            a, b = apply_map(func, range(3), range(3, 300))

        state = flow.run()
        assert state.result[a].result == [1, 2, 3]
        assert state.result[b].result == [4, 5, 6]

    @pytest.mark.parametrize("api", ["functional", "imperative"])
    def test_apply_map_control_flow(self, api):
        if api == "functional":

            def func(x):
                with case(is_even(x), True):
                    x2 = add(x, 1)
                return merge(x2, x)

            with Flow("test") as flow:
                res = apply_map(func, range(4))
        else:

            def func(x, flow):
                cond = is_even.copy().bind(x, flow=flow)
                with case(cond, True):
                    x2 = add.copy().bind(x, 1, flow=flow)
                return merge(x2, x, flow=flow)

            flow = Flow("test")
            res = apply_map(func, range(4), flow=flow)

        state = flow.run()
        assert state.result[res].result == [1, 1, 3, 3]

    def test_tasks_have_all_non_unmapped_constant_args_as_transitive_upstream_deps(
        self,
    ):
        def func(a, b, c, d):
            m = inc.copy(name="m").bind(1)
            n = inc.copy(name="n").bind(a)
            o = inc.copy(name="o").bind(b)
            p = add.copy(name="p").bind(n, o)
            q = add.copy(name="q").bind(c, d)
            r = add.copy(name="r").bind(q, m)
            return m, n, o, p, q, r

        with Flow("test") as flow:
            a = ranged.copy(name="a").bind(3)
            b = inc.copy(name="b").bind(1)
            c = Constant(1, name="c")
            d = Constant(range(3), name="d")
            m, n, o, p, q, r = apply_map(
                func, a, edges.unmapped(b), c=edges.unmapped(c), d=d
            )

        def edge_info(task):
            """Returns a map of {upstream: (is_data_dep, is_mapped)}"""
            return {
                e.upstream_task: (e.key is not None, e.mapped)
                for e in flow.edges_to(task)
            }

        assert edge_info(m) == {a: (False, True), b: (False, False), d: (False, True)}
        assert edge_info(n) == {a: (True, True), b: (False, False), d: (False, True)}
        assert edge_info(o) == {a: (False, True), b: (True, False), d: (False, True)}
        assert edge_info(p) == {n: (True, True), o: (True, True)}
        assert edge_info(q) == {a: (False, True), b: (False, False), d: (True, True)}
        assert edge_info(r) == {q: (True, True), m: (True, True)}

        state = flow.run()
        res = {t: state.result[t].result for t in [m, n, o, p, q, r]}
        sol = {
            m: [2, 2, 2],
            n: [1, 2, 3],
            o: [3, 3, 3],
            p: [4, 5, 6],
            q: [1, 2, 3],
            r: [3, 4, 5],
        }
        assert res == sol

    def test_apply_map_can_be_used_on_apply_map_result(
        self,
    ):
        # Prior to commit 4b0df740de99a1fad3182c01f4b182ba83445bcc this would introduce
        # a cycle
        @task
        def combine(item_combination):
            return item_combination[0] + item_combination[1]

        # mapping function one
        def apply_map_one(item):
            result_one = inc(item)
            result_two = inc(inc(item))
            return (result_one, result_two)

        # mapping function two
        def apply_map_two(item):
            return combine(item)

        with Flow("test") as flow:
            one_result = apply_map(apply_map_one, [1, 2, 3])
            two_result = apply_map(apply_map_two, one_result)

        state = flow.run()
        assert state.is_successful()
        assert state.result[one_result[0]].result == [2, 3, 4]
        assert state.result[one_result[1]].result == [3, 4, 5]
        assert state.result[two_result].result == [5, 7, 9]

    def test_apply_map_inside_case_statement_works(self):
        def func(x, a):
            return add(x, 1), add(x, a)

        with Flow("test") as flow:
            branch = Parameter("branch")
            with case(branch, True):
                a = inc(1)
                b, c = apply_map(func, range(4), edges.unmapped(a))
                d = add.map(b, c)

        state = flow.run(branch=True)
        assert state.result[a].result == 2
        assert state.result[b].result == [1, 2, 3, 4]
        assert state.result[c].result == [2, 3, 4, 5]
        assert state.result[d].result == [3, 5, 7, 9]

        state = flow.run(branch=False)
        assert state.result[a].is_skipped()
        assert state.result[b].is_skipped()
        assert state.result[c].is_skipped()
        assert state.result[d].is_skipped()

    def test_apply_map_inside_resource_manager_works(self):
        @resource_manager
        class MyResource:
            def setup(self):
                return 1

            def cleanup(self, _):
                pass

        def func(x, a):
            return add(x, a), add(x, 2)

        with Flow("test") as flow:
            with MyResource() as a:
                b, c = apply_map(func, range(4), edges.unmapped(a))
                d = add.map(b, c)

        state = flow.run()
        assert state.result[a].result == 1
        assert state.result[b].result == [1, 2, 3, 4]
        assert state.result[c].result == [2, 3, 4, 5]
        assert state.result[d].result == [3, 5, 7, 9]

    def test_apply_map_inputs_added_to_subflow_before_calling_func(self):
        """We need to ensure all args to `apply_map` are added to the temporary
        subflow *before* calling the mapped func. Otherwise things like
        `case`/`resource_manager` statements that check the subgraph can get
        confused and create new edges that shouldn't exist, leading to cycles."""

        def func(cond, a, b):
            with case(cond, True):
                res1 = a + 1
            with case(cond, False):
                res2 = b + 1
            return merge(res1, res2)

        @tasks.task
        def identity(x):
            return x

        with Flow("test") as flow:
            cond = identity([True, False, True])
            a = identity([1, 2, 3])
            b = identity([4, 5, 6])
            c = apply_map(func, cond, a, b)

        state = flow.run()
        assert state.result[c].result == [2, 6, 4]

    @pytest.mark.parametrize("input_type", ["constant", "task"])
    def test_apply_map_flatten_works(self, input_type):
        def func(a):
            return a * 2

        @tasks.task
        def nested_list():
            return [[1], [1, 2], [1, 2, 3]]

        constant_nested = nested_list.run()

        with Flow("test") as flow:
            nested = nested_list()
            if input_type == "constant":
                a = apply_map(func, edges.flatten(nested))
            else:
                a = apply_map(func, edges.flatten(constant_nested))

        state = flow.run()
        assert state.result[a].result == [2, 2, 4, 2, 4, 6]

    def test_apply_map_mixed_edge_types(self):
        @tasks.task
        def get_mixed_types():
            return 3, [1, 2, 3], [[1, 2], [3]]

        @tasks.task
        def identity(a, b, c):
            return a, b, c

        def func(u, m, f):
            return identity(u, m, f)

        with Flow("test") as flow:
            m = get_mixed_types()
            a = apply_map(func, edges.unmapped(m[0]), m[1], edges.flatten(m[2]))

        state = flow.run()
        assert state.result[a].result == [(3, 1, 1), (3, 2, 2), (3, 3, 3)]


class TestAsTask:
    @pytest.mark.parametrize(
        "obj",
        [
            1,
            (3, 4),
            ["a", "b"],
            "string",
            dict(x=42),
            type(None),
            lambda *args: None,
            {None: 88},
        ],
    )
    def test_as_task_with_basic_python_objs(self, obj):
        @tasks.task
        def return_val(x):
            "Necessary because constant tasks aren't tracked inside the flow"
            return x

        with Flow("test") as f:
            t = tasks.as_task(obj)
            val = return_val(t)

        assert isinstance(t, Task)
        assert t.auto_generated is True
        res = FlowRunner(f).run(return_tasks=[val])

        assert res.is_successful()
        assert res.result[val].result == obj

    def test_as_task_toggles_constants(self):
        with Flow("test"):
            t = tasks.as_task(4)

        assert isinstance(t, Task)
        assert t.name == "4"

    def test_as_task_doesnt_label_tasks_as_auto_generated(self):
        t = Task()
        assert t.auto_generated is False
        assert tasks.as_task(t).auto_generated is False

    @pytest.mark.parametrize(
        "val", [[[[]]], [[[3]]], [1, 2, (3, [4])], [([1, 2, 3],)], {"a": 1, "b": [2]}]
    )
    def test_nested_collections_of_constants_are_constants(self, val):
        task = tasks.as_task(val)
        assert isinstance(task, Constant)
        assert task.value == val

    @pytest.mark.parametrize(
        "val",
        [
            [[[3, Task()]]],
            [1, Task(), (3, [4])],
            [([1, 2, Task()],)],
            {"a": Task(), "b": [2]},
        ],
    )
    def test_nested_collections_of_mixed_constants_are_not_constants(self, val):
        with Flow("test"):
            task = tasks.as_task(val)
        assert not isinstance(task, Constant)

    @pytest.mark.parametrize(
        "val", [[[[]]], [[[3]]], [1, 2, (3, [4])], [([1, 2, 3],)], {"a": 1, "b": [2]}]
    )
    def test_nested_collections(self, val):
        with Flow("test") as f:
            task = tasks.as_task(val)
            f.add_task(task)
        assert f.run().result[task].result == val

    def test_ordered_collections(self):
        """
        Tests that ordered collections maintain order
        """
        val = [[list(range(100))]]
        with Flow("test") as f:
            task = tasks.as_task(val)
            f.add_task(task)
        assert f.run().result[task].result == val


def test_tag_contextmanager_works_with_task_decorator():
    @tasks.task
    def mytask():
        pass

    @tasks.task(tags=["default"])
    def tagged_task():
        pass

    with Flow(name="test"):
        with tasks.tags("chris"):
            res = mytask()
            other = tagged_task()

    assert res.tags == {"chris"}
    assert other.tags == {"chris", "default"}


def test_copying_then_setting_tags_doesnt_leak_backwards():
    with Flow(name="test"):
        t1 = Task()
        with tasks.tags("init-tag"):
            t2 = t1.copy()

    assert t2.tags == {"init-tag"}
    assert t1.tags == set()


def test_setting_tags_then_calling_copies_tags():
    with tasks.tags("init-tag"):
        t1 = Task()

    with Flow(name="test"):
        t2 = t1()

    assert t2.tags == {"init-tag"}


def test_context_manager_for_setting_tags():
    """
    Test setting Task tags with a context manager, including:
        - top level
        - nested
        - nested with explicit tags
    """

    with tasks.tags("1", "2"):
        t1 = Task()
        assert t1.tags == set(["1", "2"])

        with tasks.tags("3", "4"):
            t2 = Task()
            assert t2.tags == set(["1", "2", "3", "4"])

            t3 = Task(tags=["5"])
            assert t3.tags == set(["1", "2", "3", "4", "5"])


class TestPauseTask:
    def test_pause_task_pauses(self):
        class AddTask(Task):
            def run(self, x, y):
                if x == y:
                    tasks.pause_task("test message")
                return x + y

        with Flow(name="test") as f:
            t1 = AddTask()(1, 1)
        res = FlowRunner(flow=f).run(return_tasks=[t1])
        assert isinstance(res.result[t1], Paused)
        assert res.result[t1].message == "test message"

    def test_pause_task_doesnt_pause_sometimes(self):
        class OneTask(Task):
            def run(self):
                tasks.pause_task()
                return 1

        class AddTask(Task):
            def run(self, x, y):
                if x == y:
                    tasks.pause_task()
                return x + y

        with Flow(name="test") as f:
            t1 = AddTask()(1, 1)
            t2 = OneTask()(upstream_tasks=[t1])

        res = FlowRunner(flow=f).run(task_states={t1: Resume()}, return_tasks=[t1, t2])
        assert res.result[t1].is_successful()
        assert isinstance(res.result[t2], Paused)


class TestDefaultFromAttrs:
    @pytest.fixture
    def xtask(self):
        class A(Task):
            def __init__(self, x=None):
                self.x = x
                super().__init__()

            @tasks.defaults_from_attrs("x")
            def run(self, x=None):
                "Lil doc"
                return x

        return A

    @pytest.fixture
    def multitask(self):
        class B(Task):
            def __init__(self, x=None, y=None):
                self.x = x
                self.y = y
                super().__init__()

            @tasks.defaults_from_attrs("x")
            def run(self, x=None, y=None):
                return x, y

        return B

    def test_pulls_from_attr_if_not_provided_at_runtime(self, xtask):
        a = xtask(5)
        assert a.run() == 5

    def test_runtime_takes_precedence(self, xtask):
        a = xtask(5)
        assert a.run(x=6) == 6

    def test_even_none_at_runtime_takes_precedence(self, xtask):
        """
        This test ensures that `None` isn't some ambiguous special case: keywords
        provided at runtime _always_ take precedence.
        """
        a = xtask(5)
        assert a.run(x=None) is None

    def test_doc_is_unaffected(self, xtask):
        assert xtask.run.__doc__ == "Lil doc"

    def test_args_not_listed_are_unaffected(self, multitask):
        b = multitask(x=1, y=2)
        assert b.run() == (1, None)

    def test_works_with_multiple_args(self, multitask):
        b = multitask(x=1, y=2)
        assert b.run(y=3, x=55) == (55, 3)

    def test_works_with_mutiple_attrs(self):
        class TestTask(Task):
            def __init__(self, x=None, y=None):
                self.x = x
                self.y = y
                super().__init__()

            @tasks.defaults_from_attrs("x", "y")
            def run(self, x=None, y=None):
                return x, y

        task = TestTask(x=1, y=2)
        assert task.run() == (1, 2)
        assert task.run(x=4) == (4, 2)
        assert task.run(y=99) == (1, 99)
        assert task.run(x=None, y=None) == (None, None)

    def test_raises_if_attr_wasnt_set_at_init(self):
        """
        It would be nice to raise this at creation time, but unfortunately
        the information just isn't available.
        """

        class Forgot(Task):
            @tasks.defaults_from_attrs("x")
            def run(self, x=None):
                return x

        t = Forgot()
        with pytest.raises(AttributeError, match="no attribute 'x'"):
            t.run()
