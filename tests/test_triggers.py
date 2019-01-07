import pytest

from prefect.core.edge import Edge
from prefect import triggers
from prefect.engine import signals
from prefect.engine.state import Failed, Pending, Retrying, Skipped, State, Success


def generate_states(success=0, failed=0, skipped=0, pending=0, retrying=0) -> dict:
    state_counts = {
        Success: success,
        Failed: failed,
        Skipped: skipped,
        Pending: pending,
        Retrying: retrying,
    }

    states = set()
    for state, count in state_counts.items():
        for _ in range(count):
            states.add(state())
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
