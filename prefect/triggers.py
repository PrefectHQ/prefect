"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""

from prefect import exceptions


def all_success(preceding_states):
    """
    any skipped -> skip
    any unsuccessful -> fail
    """
    if any(s.is_skipped() for s in preceding_states):
        raise exceptions.SKIP(
            'Trigger failed: at least one preceding task was skipped.')
    elif not all(s.is_successful() for s in preceding_states):
        raise exceptions.FAIL(
            'Trigger failed: not all preceding tasks were successful')


def all_failed(preceding_states):
    """
    any skipped -> skip
    any successful -> fail
    """
    if any(s.is_skipped() for s in preceding_states):
        raise exceptions.SKIP(
            'Trigger failed: at least one preceding task was skipped.')
    elif not all(s.is_failed() for s in preceding_states):
        raise exceptions.FAIL(
            'Trigger failed: not all preceding tasks failed.')


def any_success(preceding_states):
    """
    all skipped -> skip
    none successful -> fail
    """
    if all(s.is_skipped() for s in preceding_states):
        raise exceptions.SKIP(
            'Trigger failed: all preceding tasks were skipped.')
    if not any(s.is_successful() for s in preceding_states):
        raise exceptions.FAIL(
            'Trigger failed: all preceding tasks failed.')


def any_failed(preceding_states):
    """
    all skipped -> skip
    none failed -> fail
    """
    if all(s.is_skipped() for s in preceding_states):
        raise exceptions.SKIP(
            'Trigger failed: all preceding tasks were skipped.')
    if not any(s.is_failed() for s in preceding_states):
        raise exceptions.FAIL(
            'Trigger failed: all preceding tasks were successful.')
