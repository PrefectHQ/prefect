"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""

from prefect import signals


def all_success(preceding_states):
    """
    any waiting -> wait
    any unsuccessful -> fail
    * skipped tasks count as successes
    """
    if any(s.is_waiting() for s in preceding_states):
        raise signals.WAIT_FOR_UPSTREAM(
            'An upstream task is waiting to continue.')
    elif not all(s.is_successful() for s in preceding_states):
        raise signals.FAIL(
            'Trigger failed: not all preceding tasks were successful')


def all_failed(preceding_states):
    """
    any waiting -> wait
    any successful -> fail
    * skipped tasks count as successes
    """
    if any(s.is_waiting() for s in preceding_states):
        raise signals.WAIT_FOR_UPSTREAM(
            'An upstream task is waiting to continue.')
    if not all(s.is_failed() for s in preceding_states):
        raise signals.FAIL(
            'Trigger failed: not all preceding tasks failed.')


def any_success(preceding_states):
    """
    none successful -> fail
    any waiting -> wait
    * skipped tasks count as successes
    """
    if not any(s.is_successful() for s in preceding_states):
        if any(s.is_waiting() for s in preceding_states):
            raise signals.WAIT_FOR_UPSTREAM(
                'An upstream task is waiting to continue.')
        raise signals.FAIL(
            'Trigger failed: all preceding tasks failed.')


def any_failed(preceding_states):
    """
    none failed -> fail
    any waiting -> wait
    * skipped tasks count as successes
    """
    if not any(s.is_failed() for s in preceding_states):
        if any(s.is_waiting() for s in preceding_states):
            raise signals.WAIT_FOR_UPSTREAM(
                'An upstream task is waiting to continue.')
        raise signals.FAIL(
            'Trigger failed: all preceding tasks were successful.')
