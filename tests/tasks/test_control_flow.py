import pytest

import prefect
from prefect import Flow, Task, task
from prefect.tasks.core.constants import Constant
from prefect.engine.state import Skipped, Success
from prefect.tasks.control_flow import ifelse, switch, merge


class Condition(Task):
    def run(self):
        return prefect.context.CONDITION


class SuccessTask(Task):
    def run(self):
        return 1


@pytest.mark.parametrize("condition_value", [True, False, "x"])
def test_ifelse(condition_value):
    condition = Condition()
    true_branch = SuccessTask(name="true branch")
    false_branch = SuccessTask(name="false branch")

    with Flow() as flow:
        cnd = ifelse(condition, true_branch, false_branch)
        assert len(flow.tasks) == 5

    with prefect.context(CONDITION=condition_value):
        state = flow.run(return_tasks=flow.tasks)

    assert isinstance(
        state.result[true_branch], Success if condition_value is True else Skipped
    )
    assert isinstance(
        state.result[false_branch], Success if condition_value is False else Skipped
    )


@pytest.mark.parametrize("condition_value", ["a", "b", "c", "d", "x"])
def test_switch(condition_value):
    condition = Condition()
    a_branch = SuccessTask(name="a")
    b_branch = SuccessTask(name="b")
    c_branch = SuccessTask(name="c")
    d_branch = SuccessTask(name="d")

    with Flow() as flow:
        switch(condition, dict(a=a_branch, b=b_branch, c=c_branch, d=d_branch))
        assert len(flow.tasks) == 9

    with prefect.context(CONDITION=condition_value):
        state = flow.run(return_tasks=flow.tasks)
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

    with Flow() as flow:
        condition = Condition()
        true_branch = [SuccessTask(name="true branch {}".format(i)) for i in range(3)]
        false_branch = [SuccessTask(name="false branch {}".format(i)) for i in range(3)]
        ifelse(condition, true_branch[0], false_branch[0])

        flow.chain(*true_branch)
        flow.chain(*false_branch)

        merge_task = merge(true_branch[-1], false_branch[-1])

    with prefect.context(CONDITION=True):
        state = flow.run(return_tasks=flow.tasks)

        for t in true_branch:
            assert isinstance(state.result[t], Success)
        for t in false_branch:
            assert isinstance(state.result[t], Skipped)
        assert isinstance(state.result[merge_task], Success)


def test_list_of_tasks():
    """
    Test that a list of tasks can be set as a switch condition, with a warning.

    The warning is raised because the tasks in the list will actually run
    """

    with Flow() as flow:
        condition = Condition()
        true_branch = [SuccessTask(), SuccessTask()]
        false_branch = SuccessTask()
        with pytest.warns(prefect.utilities.exceptions.PrefectWarning):
            ifelse(condition, true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run(return_tasks=flow.tasks)

        for t in true_branch:
            assert isinstance(state.result[t], Success)
        assert isinstance(state.result[false_branch], Skipped)

    with prefect.context(CONDITION=False):
        state = flow.run(return_tasks=flow.tasks)

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
    with pytest.raises(ValueError) as exc:
        prefect.tasks.control_flow.conditional.Merge(skip_on_upstream_skip=True)
    assert "skip_on_upstream_skip=False" in str(exc.value)


def test_merge_diamond_flow_with_results():
    condition = Condition()
    true_branch = Constant(1)
    false_branch = Constant(0)

    with Flow() as flow:
        ifelse(condition, true_branch, false_branch)
        merge_task = merge(true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run(return_tasks=flow.tasks)
        assert state.result[merge_task].result == 1

    with prefect.context(CONDITION=False):
        state = flow.run(return_tasks=flow.tasks)
        assert state.result[merge_task].result == 0

    with prefect.context(CONDITION=None):
        state = flow.run(return_tasks=flow.tasks)
        assert state.result[merge_task].result is None


def test_merge_with_list():
    with Flow() as flow:
        condition = Condition()
        true_branch = prefect.utilities.tasks.as_task([Constant(1), Constant(2)])
        false_branch = Constant(0)

        with pytest.warns(prefect.utilities.exceptions.PrefectWarning):
            ifelse(condition, true_branch, false_branch)
        merge_task = merge(true_branch, false_branch)

    with prefect.context(CONDITION=True):
        state = flow.run(return_tasks=flow.tasks)
        assert state.result[merge_task].result == [1, 2]
