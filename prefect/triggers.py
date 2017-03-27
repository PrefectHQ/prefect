"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.

Trigger is passed a State object representing the task's current state and
a dict of {task : state} pairs for all preceding tasks. It is expected to
adjust the current state as necessary.

"""

from prefect.state import State

def all_success(current_state, preceding_states):
    """
    any skipped -> skip
    any unsuccessful -> fail
    """
    if any(s.is_skipped() for s in preceding_states.values()):
        current_state.skip()
    elif not all(s.is_successful() for s in preceding_states.values()):
        current_state.fail()

def all_failed(current_state, preceding_states):
    """
    any skipped -> skip
    any successful -> fail
    """
    if any(s.is_skipped() for s in preceding_states.values()):
        current_state.skip()
    elif not all(s.is_failed() for s in preceding_states.values()):
        current_state.fail()

def any_success(current_state, preceding_states):
    """
    all skipped -> skip
    none successful -> fail
    """
    if all(s.is_skipped() for s in preceding_states.values()):
        current_state.skip()
    if not any(s.is_successful() for s in preceding_states.values()):
        current_state.fail()

def any_failed(current_state, preceding_states):
    """
    all skipped -> skip
    none failed -> fail
    """
    if all(s.is_skipped() for s in preceding_states.values()):
        current_state.skip()
    if not any(s.is_failed() for s in preceding_states.values()):
        current_state.fail()
