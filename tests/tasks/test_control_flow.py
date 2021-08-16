import pytest

import prefect
from prefect import Flow, Task, task, Parameter
from prefect.engine.state import Skipped, Success
from prefect.tasks.control_flow import FilterTask, ifelse, merge, switch, case
from prefect.tasks.control_flow.conditional import CompareValue


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


def test_merge_imperative_flow():
    flow = Flow("test")

    cond = identity.copy().bind(True, flow=flow)
    with case(cond, True):
        a = inc.copy().bind(1, flow=flow)

    with case(cond, False):
        b = inc.copy().bind(2, flow=flow)

    c = merge(a, b, flow=flow)

    state = flow.run()
    assert state.result[cond].result is True
    assert state.result[a].result == 2
    assert state.result[b].is_skipped()
    assert state.result[c].result == 2


def test_mapped_switch_and_merge():
    with Flow("iterated map") as flow:
        mapped_result = identity.copy().map(["a", "b", "c"])

        a = identity("a")
        b = identity("b")
        c = identity("c")

        switch(condition=mapped_result, cases=dict(a=a, b=b, c=c), mapped=True)

        merge_result = merge(a, b, c, mapped=True)

    state = flow.run()

    assert state.result[a].result == ["a", None, None]
    assert state.result[b].result == [None, "b", None]
    assert state.result[c].result == [None, None, "c"]
    assert state.result[merge_result].result == ["a", "b", "c"]


def test_mapped_ifelse_and_merge():
    @task
    def is_even(x):
        return x % 2 == 0

    @task
    def even():
        return "even"

    @task
    def odd():
        return "odd"

    with Flow("iterated map") as flow:
        mapped_result = is_even.map([1, 2, 3])

        ifelse(condition=mapped_result, true_task=even, false_task=odd, mapped=True)

        merge_result = merge(even, odd, flow=flow, mapped=True)

    state = flow.run()

    assert state.result[merge_result].result == ["odd", "even", "odd"]


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
        res = task.run([None, 0, 1, 5, "", ValueError()])
        assert len(res) == 4
        assert res == [0, 1, 5, ""]

    def test_filter_func_can_be_changed(self):
        task = FilterTask(filter_func=lambda r: r != 5)
        exc = ValueError()
        res = task.run([None, 0, 1, 5, "", exc])
        assert len(res) == 5
        assert res == [None, 0, 1, "", exc]

    def test_log_func(self, caplog):
        task = FilterTask(
            filter_func=lambda r: r != 5,
            log_func=lambda x: f"Valid Values: {','.join([str(y) for y in x])}",
        )
        task.run([1, 2, 3, 4, 5, 6, 7])
        assert "Valid Values: 1,2,3,4,6,7" in caplog.text


@task
def identity(x):
    return x


@task
def inc(x):
    return x + 1


class TestCase:
    def test_case_errors(self):
        with Flow("test"):
            with pytest.raises(TypeError, match="`value` cannot be a task"):
                with case(identity(True), identity(False)):
                    pass

    def test_empty_case_block_no_tasks(self):
        with Flow("test") as flow:
            cond = identity(True)
            with case(cond, True):
                pass

        # No tasks added if case block is empty
        assert flow.tasks == {cond}

    def test_case_sets_and_clears_context(self):
        with Flow("test"):
            c1 = case(identity(True), True)
            c2 = case(identity(False), True)
            assert "case" not in prefect.context
            with c1:
                assert prefect.context["case"] is c1
                with c2:
                    assert prefect.context["case"] is c2
                assert prefect.context["case"] is c1
            assert "case" not in prefect.context

    def test_case_upstream_tasks(self):
        with Flow("test") as flow:
            a = identity(0)
            with case(identity(True), True):
                b = inc(a)
                c = inc(b)
                d = identity(1)
                e = inc(d)
                f = inc(e)

        compare_values = [t for t in flow.tasks if isinstance(t, CompareValue)]
        assert len(compare_values) == 1
        comp = compare_values[0]

        assert flow.upstream_tasks(a) == set()
        assert flow.upstream_tasks(b) == {comp, a}
        assert flow.upstream_tasks(c) == {b}
        assert flow.upstream_tasks(d) == {comp}
        assert flow.upstream_tasks(e) == {d}
        assert flow.upstream_tasks(f) == {e}

    @pytest.mark.parametrize("branch", ["a", "b", "c"])
    def test_case_execution(self, branch):
        with Flow("test") as flow:
            cond = identity(branch)
            with case(cond, "a"):
                a = identity(1)
                b = inc(a)

            with case(cond, "b"):
                c = identity(3)
                d = inc(c)

            e = merge(b, d)

        state = flow.run()

        if branch == "a":
            assert state.result[a].result == 1
            assert state.result[b].result == 2
            assert state.result[c].is_skipped()
            assert state.result[d].is_skipped()
            assert state.result[e].result == 2
        elif branch == "b":
            assert state.result[a].is_skipped()
            assert state.result[b].is_skipped()
            assert state.result[c].result == 3
            assert state.result[d].result == 4
            assert state.result[e].result == 4
        elif branch == "c":
            for t in [a, b, c, d, e]:
                assert state.result[t].is_skipped()

    @pytest.mark.parametrize("branch1", [True, False])
    @pytest.mark.parametrize("branch2", [True, False])
    def test_nested_case_execution(self, branch1, branch2):
        with Flow("test") as flow:
            cond1 = identity(branch1)

            a = identity(0)
            with case(cond1, True):
                cond2 = identity(branch2)
                b = identity(10)
                with case(cond2, True):
                    c = inc(a)
                    d = inc(c)
                with case(cond2, False):
                    e = inc(b)
                    f = inc(e)

                g = merge(d, f)

            with case(cond1, False):
                h = identity(3)
                i = inc(h)

            j = merge(g, i)

        state = flow.run()

        sol = {a: 0, cond1: branch1}
        if branch1:
            sol[cond2] = branch2
            sol[b] = 10
            if branch2:
                sol[c] = 1
                sol[d] = sol[g] = sol[j] = 2
            else:
                sol[e] = 11
                sol[f] = sol[g] = sol[j] = 12
        else:
            sol[h] = 3
            sol[i] = sol[j] = 4

        for t in [cond1, cond2, a, b, c, d, e, f, g, h, i, j]:
            if t in sol:
                assert state.result[t].result == sol[t]
            else:
                assert state.result[t].is_skipped()

    def test_case_imperative_errors(self):
        flow = Flow("test")
        flow2 = Flow("test2")
        cond = identity.copy()
        a = identity.copy()
        with pytest.raises(ValueError, match="Multiple flows"):
            with case(cond, True):
                flow.add_task(a)
                flow2.add_task(a)

    @pytest.mark.parametrize("branch", ["a", "b", "c"])
    def test_case_imperative_api(self, branch):
        flow = Flow("test")

        cond = identity.copy()
        a = identity.copy()
        b = inc.copy()
        c = identity.copy()
        d = inc.copy()

        cond.bind(branch, flow=flow)
        flow.add_task(cond)
        with case(cond, "a"):
            a.bind(1, flow=flow)
            b.bind(a, flow=flow)
            flow.add_task(a)
            flow.add_task(b)

        with case(cond, "b"):
            c.bind(3, flow=flow)
            d.bind(c, flow=flow)
            flow.add_task(c)
            flow.add_task(d)

        state = flow.run()

        if branch == "a":
            assert state.result[a].result == 1
            assert state.result[b].result == 2
            assert state.result[c].is_skipped()
            assert state.result[d].is_skipped()
        elif branch == "b":
            assert state.result[a].is_skipped()
            assert state.result[b].is_skipped()
            assert state.result[c].result == 3
            assert state.result[d].result == 4
        elif branch == "c":
            for t in [a, b, c, d]:
                assert state.result[t].is_skipped()

    def test_case_with_parameters(self):
        with Flow("test") as flow:
            x = Parameter("x")
            cond = identity(True)
            with case(cond, True):
                y1 = x + 1
            with case(cond, False):
                y2 = x - 1

        state = flow.run(x=1)
        assert state.result[y1].result == 2
        assert state.result[y2].is_skipped()

    def test_case_with_constants(self):
        with Flow("test") as flow:
            cond = identity(True)
            with case(cond, True):
                res = inc.map(range(4))
            with case(cond, False):
                res2 = inc.map(range(4))

        state = flow.run()
        assert state.result[res].result == [1, 2, 3, 4]
        assert state.result[res2].is_skipped()
