import pytest

import prefect
from prefect import Flow, Task, task
from prefect.engine.result import NoResult
from prefect.engine.state import Skipped, Success
from prefect.tasks.control_flow import FilterTask, ifelse, merge, switch
from prefect.tasks.core.constants import Constant


class Condition(Task):
    def run(self):
        return prefect.context.CONDITION


class SuccessTask(Task):
    def run(self):
        return 1


@pytest.mark.parametrize("condition_value", [True, False])
def test_ifelse(condition_value):
    condition = Condition()
    true_branch = SuccessTask(name="true branch")
    false_branch = SuccessTask(name="false branch")

    with Flow(name="test") as flow:
        cnd = ifelse(condition, true_branch, false_branch)
        assert len(flow.tasks) == 6

    with prefect.context(CONDITION=condition_value):
        state = flow.run()

    assert isinstance(
        state.result[true_branch], Success if condition_value is True else Skipped
    )
    assert isinstance(
        state.result[false_branch], Success if condition_value is False else Skipped
    )


@pytest.mark.parametrize("condition_value", [True, False])
def test_ifelse_doesnt_add_None_task(condition_value):
    condition = Condition()
    true_branch = SuccessTask(name="true branch")

    with Flow(name="test") as flow:
        cnd = ifelse(condition, true_branch, None)
        assert len(flow.tasks) == 4

    with prefect.context(CONDITION=condition_value):
        state = flow.run()

    assert isinstance(
        state.result[true_branch], Success if condition_value is True else Skipped
    )


@pytest.mark.parametrize("condition_value", [1, "a", "False", True, [1], {1: 2}])
def test_ifelse_with_truthy_conditions(condition_value):
    condition = Condition()
    true_branch = SuccessTask(name="true branch")
    false_branch = SuccessTask(name="false branch")

    with Flow(name="test") as flow:
        cnd = ifelse(condition, true_branch, false_branch)

    with prefect.context(CONDITION=condition_value):
        state = flow.run()

    assert state.result[true_branch].is_successful()
    assert state.result[false_branch].is_skipped()


@pytest.mark.parametrize("condition_value", [0, "", None, False, [], {}])
def test_ifelse_with_falsey_conditions(condition_value):
    condition = Condition()
    true_branch = SuccessTask(name="true branch")
    false_branch = SuccessTask(name="false branch")

    with Flow(name="test") as flow:
        cnd = ifelse(condition, true_branch, false_branch)

    with prefect.context(CONDITION=condition_value):
        state = flow.run()

    assert state.result[true_branch].is_skipped()
    assert state.result[false_branch].is_successful()


@pytest.mark.parametrize("condition_value", ["a", "b", "c", "d", "x"])
def test_switch(condition_value):
    condition = Condition()
    a_branch = SuccessTask(name="a")
    b_branch = SuccessTask(name="b")
    c_branch = SuccessTask(name="c")
    d_branch = SuccessTask(name="d")

    with Flow(name="test") as flow:
        switch(condition, dict(a=a_branch, b=b_branch, c=c_branch, d=d_branch))
        assert len(flow.tasks) == 9

    with prefect.context(CONDITION=condition_value):
        state = flow.run()
        assert isinstance(
            state.result[a_branch], Success if condition_value == "a" else Skipped
        )
        assert isinstance(
            state.result[b_branch], Success if condition_value == "b" else Skipped
        )
        assert isinstance(
            state.result[c_branch], Success if condition_value == "c" else Skipped
        )
        assert isinstance(
            state.result[d_branch], Success if condition_value == "d" else Skipped
        )


def test_merging_diamond_flow():
    """
    Test a flow that branches into two separate chains that later merge back together.

    One branch should all get skipped but the merge task should not skip.
    """

    with Flow(name="test") as flow:
        condition = Condition()
        true_branch = [SuccessTask(name="true branch {}".format(i)) for i in range(3)]
        false_branch = [SuccessTask(name="false branch {}".format(i)) for i in range(3)]
        ifelse(condition, true_branch[0], false_branch[0])

        flow.chain(*true_branch)
        flow.chain(*false_branch)

        merge_task = merge(true_branch[-1], false_branch[-1])

    with prefect.context(CONDITION=True):
        state = flow.run()

        for t in true_branch:
            assert isinstance(state.result[t], Success)
        for t in false_branch:
            assert isinstance(state.result[t], Skipped)
        assert isinstance(state.result[merge_task], Success)


def test_merging_with_objects_that_cant_be_equality_compared():
    class SpecialObject:
        def __eq__(self, other):
            return self

        def __bool__(self):
            raise SyntaxError("You can't handle the truth!")

    @task
    def return_array():
        return SpecialObject()

    with Flow("test-merge") as flow:
        success = SuccessTask()
        ifelse(Condition(), success, return_array)
        merge_task = merge(success, return_array)

    with prefect.context(CONDITION=False):
        flow_state = flow.run()
    assert flow_state.is_successful()
    assert isinstance(flow_state.result[merge_task].result, SpecialObject)


def test_merging_skips_if_all_upstreams_skip():
    @task
    def skip_task():
        raise prefect.engine.signals.SKIP("not today")

    with Flow("skipper") as flow:
        merge_task = merge(skip_task(), skip_task())

    flow_state = flow.run()
    assert flow_state.is_successful()
    assert flow_state.result[merge_task].is_skipped()
    assert flow_state.result[merge_task].result is None


def test_list_of_tasks():
    """
    Test that a list of tasks can be set as a switch condition
    """

    with Flow(name="test") as flow:
        condition = Condition()
        true_branch = [SuccessTask(), SuccessTask()]
        false_branch = SuccessTask()
        ifelse(condition, true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run()

        for t in true_branch:
            assert isinstance(state.result[t], Success)
        assert isinstance(state.result[false_branch], Skipped)

    with prefect.context(CONDITION=False):
        state = flow.run()

        for t in true_branch:
            # the tasks in the list ran becuase they have no upstream dependencies.
            assert isinstance(state.result[t], Success)
        list_task = next(
            t for t in flow.tasks if isinstance(t, prefect.tasks.core.collections.List)
        )
        # but the list itself skipped
        assert isinstance(state.result[list_task], Skipped)
        assert isinstance(state.result[false_branch], Success)


def test_merge_with_upstream_skip_arg_raises_error():
    with pytest.raises(ValueError, match="skip_on_upstream_skip=False"):
        prefect.tasks.control_flow.conditional.Merge(skip_on_upstream_skip=True)


def test_merge_diamond_flow_with_results():
    condition = Condition()

    @task
    def true_branch():
        return 1

    @task
    def false_branch():
        return 0

    with Flow(name="test") as flow:
        ifelse(condition, true_branch, false_branch)
        merge_task = merge(true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run()
        assert state.result[merge_task].result == 1

    with prefect.context(CONDITION=False):
        state = flow.run()
        assert state.result[merge_task].result == 0


def test_merge_can_distinguish_between_a_none_result_and_an_unrun_task():
    condition = Condition()

    @task
    def true_branch():
        return None

    @task
    def false_branch():
        return 0

    with Flow(name="test") as flow:
        ifelse(condition, true_branch, false_branch)
        merge_task = merge(true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run()
        assert state.result[merge_task].result is None


def test_merge_with_list():
    @task
    def false_branch():
        return 0

    @task
    def true_branch():
        return [1, 2]

    with Flow(name="test") as flow:
        condition = Condition()
        ifelse(condition, true_branch, false_branch)
        merge_task = merge(true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run()
        assert state.result[merge_task].result == [1, 2]


def test_merge_order():
    @task
    def x():
        return "x"

    @task
    def y():
        return "y"

    with Flow(name="test") as flow:
        merge_task = merge(x(), y())

    state = flow.run()
    assert state.result[merge_task].result == "x"


class TestFilterTask:
    def test_empty_initialization(self):
        task = FilterTask()
        assert task.name == "FilterTask"
        assert task.skip_on_upstream_skip is False
        assert task.trigger == prefect.triggers.all_finished

    def test_skip_on_upstream_skip_can_be_overwritten(self):
        task = FilterTask(skip_on_upstream_skip=True)
        assert task.skip_on_upstream_skip is True

    def test_trigger_can_be_overwritten(self):
        task = FilterTask(trigger=prefect.triggers.manual_only)
        assert task.trigger == prefect.triggers.manual_only

    def test_default_filter_func_filters_noresults_and_exceptions(self):
        task = FilterTask()
        res = task.run([NoResult, NoResult, 0, 1, 5, "", ValueError()])
        assert len(res) == 4
        assert res == [0, 1, 5, ""]

    def test_filter_func_can_be_changed(self):
        task = FilterTask(filter_func=lambda r: r != 5)
        exc = ValueError()
        res = task.run([NoResult, NoResult, 0, 1, 5, "", exc])
        assert len(res) == 6
        assert res == [NoResult, NoResult, 0, 1, "", exc]
