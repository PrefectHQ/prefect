"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""

from prefect import signals


def all_successful(preceding_states):
    """
    any unsuccessful -> fail
    * skipped tasks count as successes
    """
    if not all(s.is_successful() for s in preceding_states.values()):
        raise signals.FAIL(
            'Trigger failed: some preceding tasks failed')
    return True


def all_failed(preceding_states):
    """
    any successful -> fail
    * skipped tasks count as successes
    """
    if not all(s.is_failed() for s in preceding_states.values()):
        raise signals.FAIL('Trigger failed: some preceding tasks succeeded')
    return True


def all_done(preceding_states):
    """
    the task always runs when upstream tasks have run
    """
    if not all(s.is_finished() for s in preceding_states.values()):
        raise signals.FAIL(
            'Trigger failed: some preceding tasks did not finish')
    return True


def any_successful(preceding_states):
    """
    none successful -> fail
    * skipped tasks count as successes
    """
    if not any(s.is_successful() for s in preceding_states.values()):
        raise signals.FAIL('Trigger failed: no preceding tasks succeeded')
    return True


def any_failed(preceding_states):
    """
    none failed -> fail
    * skipped tasks count as successes
    """
    if not any(s.is_failed() for s in preceding_states.values()):
        raise signals.FAIL('Trigger failed: no preceding tasks failed')
    return True
