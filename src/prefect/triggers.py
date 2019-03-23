"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""
from typing import Set, Callable
from prefect import context
from prefect.engine import signals, state


def all_finished(upstream_states: Set["state.State"]) -> bool:
    """
    This task will run no matter what the upstream states are, as long as they are finished.

    Args:
        - upstream_states (set[State]): the set of all upstream states
    """
    if not all(s.is_finished() for s in upstream_states):
        raise signals.TRIGGERFAIL(
            'Trigger was "all_finished" but some of the upstream tasks were not finished.'
        )

    return True


def manual_only(upstream_states: Set["state.State"]) -> bool:
    """
    This task will never run automatically, because this trigger will
    always place the task in a Paused state. The only exception is if
    the "resume" keyword is found in the Prefect context, which happens
    automatically when a task starts in a Resume state.

    Args:
        - upstream_states (set[State]): the set of all upstream states
    """
    if context.get("resume"):
        return True

    raise signals.PAUSE('Trigger function is "manual_only"')


def all_successful(upstream_states: Set["state.State"]) -> bool:
    """
    Runs if all upstream tasks were successful. Note that `SKIPPED` tasks are considered
    successes and `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (set[State]): the set of all upstream states
    """

    if not all(s.is_successful() for s in upstream_states):
        raise signals.TRIGGERFAIL(
            'Trigger was "all_successful" but some of the upstream tasks failed.'
        )
    return True


def all_failed(upstream_states: Set["state.State"]) -> bool:
    """
    Runs if all upstream tasks failed. Note that `SKIPPED` tasks are considered successes
    and `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (set[State]): the set of all upstream states
    """

    if not all(s.is_failed() for s in upstream_states):
        raise signals.TRIGGERFAIL(
            'Trigger was "all_failed" but some of the upstream tasks succeeded.'
        )
    return True


def any_successful(upstream_states: Set["state.State"]) -> bool:
    """
    Runs if any tasks were successful. Note that `SKIPPED` tasks are considered successes
    and `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (set[State]): the set of all upstream states
    """

    if not any(s.is_successful() for s in upstream_states):
        raise signals.TRIGGERFAIL(
            'Trigger was "any_successful" but none of the upstream tasks succeeded.'
        )
    return True


def any_failed(upstream_states: Set["state.State"]) -> bool:
    """
    Runs if any tasks failed. Note that `SKIPPED` tasks are considered successes and
    `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (set[State]): the set of all upstream states
    """

    if not any(s.is_failed() for s in upstream_states):
        raise signals.TRIGGERFAIL(
            'Trigger was "any_failed" but none of the upstream tasks failed.'
        )
    return True


# aliases
always_run = all_finished  # type: Callable[[Set["state.State"]], bool]
