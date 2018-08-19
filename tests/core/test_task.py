import json
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


class TestMagicInteractionMethods:
    # -----------------------------------------
    # getitem

    def test_getitem_list(self):
        with Flow() as f:
            z = Parameter("x")[Parameter("y")]
        state = f.run(parameters=dict(x=[1, 2, 3], y=1), return_tasks=[z])
        assert state.result[z].result == 2

    def test_getitem_dict(self):
        with Flow() as f:
            z = Parameter("x")[Parameter("y")]
        state = f.run(parameters=dict(x=dict(a=1, b=2, c=3), y="b"), return_tasks=[z])
        assert state.result[z].result == 2

    def test_getitem_constant(self):
        with Flow() as f:
            z = Parameter("x")["b"]
        state = f.run(parameters=dict(x=dict(a=1, b=2, c=3)), return_tasks=[z])
        assert state.result[z].result == 2

    # -----------------------------------------
    # or / pipe / |

    def test_or(self):
        with Flow() as f:
            t1 = Task()
            t2 = Task()
            t1 | t2
        assert Edge(t1, t2) in f.edges

    def test_or_with_constant(self):
        with Flow() as f:
            t1 = Task()
            t1 | 1
        assert len(f.tasks) == 2
        assert len(f.edges) == 1

    def test_ror_with_constant(self):
        with Flow() as f:
            t1 = Task()
            1 | t1
        assert len(f.tasks) == 2
        assert len(f.edges) == 1

    # -----------------------------------------
    # Chain

    def test_chained_operators(self):
        with Flow() as f:
            t1 = Task("t1")
            t2 = Task("t2")
            t3 = Task("t3")
            t4 = Task("t4")
            t5 = Task("t5")
            t6 = Task("t6")

            (t1 | t2 | t3 | t4)

        assert all([e in f.edges for e in [Edge(t1, t2), Edge(t2, t3), Edge(t3, t4)]])


class TestMagicOperatorMethods:
    # -----------------------------------------
    # addition

    def test_addition(self):
        with Flow() as f:
            z = Parameter("x") + Parameter("y")
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[z])
        assert state.result[z].result == 3

    def test_addition_with_constant(self):
        with Flow() as f:
            z = Parameter("x") + 10
        state = f.run(parameters=dict(x=1), return_tasks=[z])
        assert state.result[z].result == 11

    def test_right_addition(self):
        with Flow() as f:
            z = 10 + Parameter("x")
        state = f.run(parameters=dict(x=1), return_tasks=[z])
        assert state.result[z].result == 11

    # -----------------------------------------
    # subtraction

    def test_subtraction(self):
        with Flow() as f:
            z = Parameter("x") - Parameter("y")
        state = f.run(parameters=dict(x=1, y=2), return_tasks=[z])
        assert state.result[z].result == -1

    def test_subtraction_with_constant(self):
        with Flow() as f:
            z = Parameter("x") - 10
        state = f.run(parameters=dict(x=1), return_tasks=[z])
        assert state.result[z].result == -9

    def test_right_subtraction(self):
        with Flow() as f:
            z = 10 - Parameter("x")
        state = f.run(parameters=dict(x=1), return_tasks=[z])
        assert state.result[z].result == 9

    # -----------------------------------------
    # multiplication

    def test_multiplication(self):
        with Flow() as f:
            z = Parameter("x") * Parameter("y")
        state = f.run(parameters=dict(x=2, y=3), return_tasks=[z])
        assert state.result[z].result == 6

    def test_multiplication_with_constant(self):
        with Flow() as f:
            z = Parameter("x") * 10
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result == 20

    def test_right_multiplication(self):
        with Flow() as f:
            z = 10 * Parameter("x")
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result == 20

    # -----------------------------------------
    # division

    def test_division(self):
        with Flow() as f:
            z = Parameter("x") / Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result == 2.5

    def test_division_with_constant(self):
        with Flow() as f:
            z = Parameter("x") / 10
        state = f.run(parameters=dict(x=35), return_tasks=[z])
        assert state.result[z].result == 3.5

    def test_right_division(self):
        with Flow() as f:
            z = 10 / Parameter("x")
        state = f.run(parameters=dict(x=4), return_tasks=[z])
        assert state.result[z].result == 2.5

    # -----------------------------------------
    # floor division

    def test_floor_division(self):
        with Flow() as f:
            z = Parameter("x") // Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result == 2

    def test_floor_division_with_constant(self):
        with Flow() as f:
            z = Parameter("x") // 10
        state = f.run(parameters=dict(x=38), return_tasks=[z])
        assert state.result[z].result == 3

    def test_right_floor_division(self):
        with Flow() as f:
            z = 10 // Parameter("x")
        state = f.run(parameters=dict(x=4), return_tasks=[z])
        assert state.result[z].result == 2

    # -----------------------------------------
    # mod

    def test_mod(self):
        with Flow() as f:
            z = Parameter("x") % Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result == 1

    def test_mod_with_constant(self):
        with Flow() as f:
            z = Parameter("x") % 10
        state = f.run(parameters=dict(x=12), return_tasks=[z])
        assert state.result[z].result == 2

    def test_right_mod(self):
        with Flow() as f:
            z = 10 % Parameter("x")
        state = f.run(parameters=dict(x=14), return_tasks=[z])
        assert state.result[z].result == 10

    # -----------------------------------------
    # pow

    def test_pow(self):
        with Flow() as f:
            z = Parameter("x") ** Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result == 25

    def test_pow_with_constant(self):
        with Flow() as f:
            z = Parameter("x") ** 3
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result == 8

    def test_right_pow(self):
        with Flow() as f:
            z = 10 ** Parameter("x")
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result == 100

    # -----------------------------------------
    # gt

    def test_gt(self):
        with Flow() as f:
            z = Parameter("x") > Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result is True

    def test_gt_with_constant(self):
        with Flow() as f:
            z = Parameter("x") > 3
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result is False

    def test_right_gt(self):
        with Flow() as f:
            z = 10 > Parameter("x")
        state = f.run(parameters=dict(x=10), return_tasks=[z])
        assert state.result[z].result is False

    # -----------------------------------------
    # gte

    def test_gte(self):
        with Flow() as f:
            z = Parameter("x") >= Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result is True

    def test_gte_with_constant(self):
        with Flow() as f:
            z = Parameter("x") >= 3
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result is False

    def test_right_gte(self):
        with Flow() as f:
            z = 10 >= Parameter("x")
        state = f.run(parameters=dict(x=10), return_tasks=[z])
        assert state.result[z].result is True

    # -----------------------------------------
    # lt

    def test_lt(self):
        with Flow() as f:
            z = Parameter("x") < Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result is False

    def test_lt_with_constant(self):
        with Flow() as f:
            z = Parameter("x") < 3
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result is True

    def test_right_lt(self):
        with Flow() as f:
            z = 10 < Parameter("x")
        state = f.run(parameters=dict(x=10), return_tasks=[z])
        assert state.result[z].result is False

    # -----------------------------------------
    # lte

    def test_lte(self):
        with Flow() as f:
            z = Parameter("x") <= Parameter("y")
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result is False

    def test_lte_with_constant(self):
        with Flow() as f:
            z = Parameter("x") <= 3
        state = f.run(parameters=dict(x=2), return_tasks=[z])
        assert state.result[z].result is True

    def test_right_lte(self):
        with Flow() as f:
            z = 10 <= Parameter("x")
        state = f.run(parameters=dict(x=10), return_tasks=[z])
        assert state.result[z].result is True

    # -----------------------------------------
    # and

    def test_and(self):
        with Flow() as f:
            z = Parameter("x") & Parameter("y")
        state = f.run(parameters=dict(x=True, y=False), return_tasks=[z])
        assert state.result[z].result is False

        state = f.run(parameters=dict(x=True, y=True), return_tasks=[z])
        assert state.result[z].result is True

        state = f.run(parameters=dict(x=False, y=True), return_tasks=[z])
        assert state.result[z].result is False

        state = f.run(parameters=dict(x=False, y=False), return_tasks=[z])
        assert state.result[z].result is False

    def test_and_with_constant(self):
        with Flow() as f:
            z = Parameter("x") & True
        state = f.run(parameters=dict(x=True), return_tasks=[z])
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=False), return_tasks=[z])
        assert state.result[z].result is False

        with Flow() as f:
            z = Parameter("x") & False
        state = f.run(parameters=dict(x=True), return_tasks=[z])
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=False), return_tasks=[z])
        assert state.result[z].result is False

    def test_right_and(self):
        with Flow() as f:
            z = True & Parameter("x")
        state = f.run(parameters=dict(x=True), return_tasks=[z])
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=False), return_tasks=[z])
        assert state.result[z].result is False
        with Flow() as f:
            z = False & Parameter("x")
        state = f.run(parameters=dict(x=True), return_tasks=[z])
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=False), return_tasks=[z])
        assert state.result[z].result is False


class TestNonMagicOperatorMethods:
    def test_equals(self):
        with Flow() as f:
            z = Parameter("x").is_equal(Parameter("y"))
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=5, y=5), return_tasks=[z])
        assert state.result[z].result is True

    def test_not_equals(self):
        with Flow() as f:
            z = Parameter("x").is_not_equal(Parameter("y"))
        state = f.run(parameters=dict(x=5, y=2), return_tasks=[z])
        assert state.result[z].result is True
        state = f.run(parameters=dict(x=5, y=5), return_tasks=[z])
        assert state.result[z].result is False

    def test_not(self):
        with Flow() as f:
            z = Parameter("x").not_()
        state = f.run(parameters=dict(x=True), return_tasks=[z])
        assert state.result[z].result is False
        state = f.run(parameters=dict(x=False), return_tasks=[z])
        assert state.result[z].result is True
