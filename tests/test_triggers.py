import cloudpickle
import pytest

from prefect import context, triggers
from prefect.core.edge import Edge, Task
from prefect.engine import signals
from prefect.engine.state import (
    Failed,
    Pending,
    Resume,
    Retrying,
    Skipped,
    State,
    Success,
)


def generate_states(success=0, failed=0, skipped=0, pending=0, retrying=0) -> dict:
    state_counts = {
        Success: success,
        Failed: failed,
        Skipped: skipped,
        Pending: pending,
        Retrying: retrying,
    }

    states = dict()
    for state, count in state_counts.items():
        for _ in range(count):
            states[Edge(Task(), Task())] = state()
    return states


def test_all_successful_with_all_success():
    # True when all successful
    assert triggers.all_successful(generate_states(success=3))


def test_all_successful_with_all_success_or_skipped():
    # True when all successful or skipped
    assert triggers.all_successful(generate_states(success=3, skipped=3))


def test_all_successful_with_all_failed():
    # Fail when all fail
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.all_successful(generate_states(failed=3))


def test_all_successful_with_some_failed():
    # Fail when some fail
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.all_successful(generate_states(failed=3, success=1))


def test_not_all_skipped_with_all_success():
    # True when all successful
    assert triggers.not_all_skipped(generate_states(success=3))


def test_not_all_skipped_with_all_skipped():
    with pytest.raises(signals.SKIP) as exc:
        assert triggers.not_all_skipped(generate_states(skipped=3))


def test_not_all_skipped_with_all_success_or_skipped():
    # True when all successful or skipped
    assert triggers.not_all_skipped(generate_states(success=3, skipped=3))


def test_not_all_skipped_with_all_failed():
    # Fail when all fail
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.not_all_skipped(generate_states(failed=3))


def test_not_all_skipped_with_some_failed():
    # Fail when some fail
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.not_all_skipped(generate_states(failed=3, success=1))


def test_all_failed_with_all_failed():
    assert triggers.all_failed(generate_states(failed=3))


def test_all_failed_with_some_success():
    with pytest.raises(signals.TRIGGERFAIL):
        assert triggers.all_failed(generate_states(failed=3, success=1))


def test_all_failed_with_some_skips():
    with pytest.raises(signals.TRIGGERFAIL):
        assert triggers.all_failed(generate_states(failed=3, skipped=1))


def test_always_run_with_all_success():
    assert triggers.always_run(generate_states(success=3))


def test_always_run_with_all_failed():
    assert triggers.always_run(generate_states(failed=3))


def test_always_run_with_mixed_states():

    with pytest.raises(signals.TRIGGERFAIL):
        triggers.always_run(generate_states(success=1, failed=1, skipped=1, retrying=1))


def test_manual_only_with_all_success():
    with pytest.raises(signals.PAUSE):
        triggers.manual_only(generate_states(success=3))


def test_manual_only_with_all_failed():
    with pytest.raises(signals.PAUSE):
        triggers.manual_only(generate_states(failed=3))


def test_manual_only_with_mixed_states():
    with pytest.raises(signals.PAUSE):
        triggers.manual_only(generate_states(success=1, failed=1, skipped=1))


def test_manual_only_with_resume_in_context():
    """manual only passes when resume = True in context"""
    with context(resume=True):
        assert triggers.manual_only(generate_states(success=1, failed=1, skipped=1))


def test_manual_only_with_resume_state():
    """Passing a resume state from upstream should have no impact"""
    with pytest.raises(signals.PAUSE):
        triggers.manual_only({Success(), Resume()})


def test_manual_only_with_empty_set():
    with pytest.raises(signals.PAUSE):
        triggers.manual_only(set())


def test_manual_only_with_empty_set_and_resume_in_context():
    with context(resume=True):
        assert triggers.manual_only(set()) is True


def test_all_finished_with_all_success():
    assert triggers.all_finished(generate_states(success=3))


def test_all_finished_with_all_failed():
    assert triggers.all_finished(generate_states(failed=3))


def test_all_finished_with_mixed_states():
    assert triggers.all_finished(generate_states(success=1, failed=1, skipped=1))


def test_all_finished_with_some_pending():
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.all_finished(generate_states(success=1, pending=1))


def test_any_successful_with_all_success():
    assert triggers.any_successful(generate_states(success=3))


def test_any_successful_with_some_success_and_some_skip():
    assert triggers.any_successful(generate_states(success=3, skipped=3))


def test_any_successful_with_some_failed_and_1_success():
    assert triggers.any_successful(generate_states(failed=3, success=1))


def test_any_successful_with_some_failed_and_1_skip():
    assert triggers.any_successful(generate_states(failed=3, skipped=1))


def test_any_successful_with_all_failed():
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.any_successful(generate_states(failed=3))


def test_any_failed_with_all_failed():
    assert triggers.any_failed(generate_states(failed=3))


def test_any_failed_with_some_failed_and_some_skipped():
    assert triggers.any_failed(generate_states(failed=3, skipped=3))


def test_any_failed_with_some_failed_and_1_success():
    assert triggers.any_failed(generate_states(failed=3, success=1))


def test_any_failed_with_all_success():
    with pytest.raises(signals.TRIGGERFAIL):
        triggers.any_failed(generate_states(success=3))


@pytest.mark.parametrize(
    "states",
    [
        generate_states(failed=3),
        generate_states(failed=1, success=2),
        generate_states(),
    ],
)
def test_some_failed_with_no_args(states):
    assert triggers.some_failed(states)


def test_some_failed_error_msg():
    trigger = triggers.some_failed(at_least=23)
    with pytest.raises(signals.TRIGGERFAIL, match="some_failed"):
        trigger(generate_states(success=1))


def test_some_failed_with_one_arg():
    trigger = triggers.some_failed(at_least=4)
    assert trigger(generate_states(failed=4, skipped=2))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=3))

    trigger = triggers.some_failed(at_most=4)
    assert trigger(generate_states(failed=4, skipped=2))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=5))


@pytest.mark.parametrize("at_least,at_most", [(1, 1), (0.2, 1), (0.01, 20)])
def test_some_failed_with_all_success(at_least, at_most):
    trigger = triggers.some_failed(at_least=at_least, at_most=at_most)
    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=3))


def test_some_failed_does_the_math():
    trigger = triggers.some_failed(at_least=0.1, at_most=2)
    assert trigger(generate_states(failed=2, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=1, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=3, pending=18))

    trigger = triggers.some_failed(at_least=2, at_most=0.1)
    assert trigger(generate_states(failed=2, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=1, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=3, pending=18))


def test_some_failed_is_pickleable():
    trigger = triggers.some_failed(at_least=0.1, at_most=2)
    new_trigger = cloudpickle.loads(cloudpickle.dumps(trigger))
    assert new_trigger(generate_states(failed=2, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        new_trigger(generate_states(failed=1, pending=18))


@pytest.mark.parametrize(
    "states",
    [
        generate_states(failed=3),
        generate_states(failed=1, success=2),
        generate_states(),
    ],
)
def test_some_successful_with_no_args(states):
    assert triggers.some_successful(states)


def test_some_successful_error_msg():
    trigger = triggers.some_successful(at_least=23)
    with pytest.raises(signals.TRIGGERFAIL, match="some_successful"):
        trigger(generate_states(success=1))


def test_some_successful_with_one_arg():
    trigger = triggers.some_successful(at_least=4)
    assert trigger(generate_states(success=4, failed=2))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=3))

    trigger = triggers.some_successful(at_most=4)
    assert trigger(generate_states(failed=4, pending=5))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=5))


@pytest.mark.parametrize("at_least,at_most", [(1, 1), (0.2, 1), (0.01, 20)])
def test_some_successful_with_all_failed(at_least, at_most):
    trigger = triggers.some_successful(at_least=at_least, at_most=at_most)
    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(failed=3))


def test_some_successful_does_the_math():
    trigger = triggers.some_successful(at_least=0.1, at_most=2)
    assert trigger(generate_states(success=2, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=1, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=3, pending=18))

    trigger = triggers.some_successful(at_least=2, at_most=0.1)
    assert trigger(generate_states(success=2, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=1, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        trigger(generate_states(success=3, pending=18))


def test_some_successful_is_pickleable():
    trigger = triggers.some_successful(at_least=0.1, at_most=2)
    new_trigger = cloudpickle.loads(cloudpickle.dumps(trigger))
    assert new_trigger(generate_states(success=2, pending=18))

    with pytest.raises(signals.TRIGGERFAIL):
        new_trigger(generate_states(success=1, pending=18))


@pytest.mark.parametrize(
    "trigger",
    [
        triggers.all_failed,
        triggers.all_finished,
        triggers.all_successful,
        triggers.always_run,
        triggers.any_failed,
        triggers.any_successful,
    ],
)
def test_standard_triggers_return_true_for_empty_upstream(trigger):
    assert trigger(dict()) is True


@pytest.mark.parametrize("func", [triggers.some_failed, triggers.some_successful])
def test_stateful_triggers_return_true_for_empty_upstream(func):
    assert func()(set()) is True
    assert func(at_least=2, at_most=4)(set()) is True
    assert func(at_least=0.1, at_most=0.5)(set()) is True
