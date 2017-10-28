import pytest
from prefect import triggers, signals
from prefect_engine.state import TaskRunState


def states(
        success=0,
        failed=0,
        skipped=0,
        skip_downstream=0,
        pending=0,
        pending_retry=0):
    state_counts = {
        TaskRunState.SUCCESS: success,
        TaskRunState.FAILED: failed,
        TaskRunState.SKIPPED: skipped,
        TaskRunState.SKIP_DOWNSTREAM: skip_downstream,
        TaskRunState.PENDING: pending,
        TaskRunState.PENDING_RETRY: pending_retry
    }

    states = {}
    for state, count in state_counts.items():
        for i in range(count):
            states[str(len(states))] = TaskRunState(state)
    return states


def test_all_successful():
    # True when all successful
    assert triggers.all_successful(states(success=3))

    # True when all successful or skipped
    assert triggers.all_successful(states(success=3, skipped=3))

    # Fail when all fail
    with pytest.raises(signals.FAIL):
        triggers.all_successful(states(failed=3))

    # Fail when some fail
    with pytest.raises(signals.FAIL):
        triggers.all_successful(states(failed=3, success=1))


def test_all_failed():
    assert triggers.all_failed(states(failed=3))
    with pytest.raises(signals.FAIL):
        assert triggers.all_failed(states(failed=3, success=1))
    with pytest.raises(signals.FAIL):
        assert triggers.all_failed(states(failed=3, skipped=1))


def test_always_run():
    assert triggers.always_run(states(success=3))
    assert triggers.always_run(states(failed=3))
    assert triggers.always_run(states(skip_downstream=3))
    assert triggers.always_run(
        states(success=1, failed=1, skipped=1, skip_downstream=1))


def test_never_run():
    assert not triggers.never_run(states(success=3))
    assert not triggers.never_run(states(failed=3))
    assert not triggers.never_run(states(skip_downstream=3))
    assert not triggers.never_run(
        states(success=1, failed=1, skipped=1, skip_downstream=1))


def test_all_finished():
    assert triggers.all_finished(states(success=3))
    assert triggers.all_finished(states(failed=3))
    assert triggers.all_finished(states(skip_downstream=3))
    assert triggers.all_finished(
        states(success=1, failed=1, skipped=1, skip_downstream=1))
    with pytest.raises(signals.FAIL):
        triggers.all_finished(states(success=1, pending=1))


def test_any_successful():
    assert triggers.any_successful(states(success=3))
    assert triggers.any_successful(states(success=3, skipped=3))
    assert triggers.any_successful(states(failed=3, success=1))
    assert triggers.any_successful(states(failed=3, skipped=1))
    with pytest.raises(signals.FAIL):
        triggers.any_successful(states(failed=3))


def test_any_failed():
    assert triggers.any_failed(states(failed=3))
    assert triggers.any_failed(states(failed=3, skipped=3))
    assert triggers.any_failed(states(failed=3, success=1))
    assert triggers.any_failed(states(failed=3, skipped=1))
    with pytest.raises(signals.FAIL):
        triggers.any_failed(states(success=3))
