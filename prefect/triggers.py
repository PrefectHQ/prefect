"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""
from typing import TYPE_CHECKING, Dict, Iterable

from prefect import signals
from prefect.utilities.json import serializable

if TYPE_CHECKING:
    from prefect.engine.state import State
    from prefect.core import Task


def always_run(upstream_states: Dict["Task", "State"]) -> bool:
    """
    This task will run no matter what the upstream states are.
    """

    return True


def manual_only(upstream_states: Dict["Task", "State"]) -> bool:
    """
    This task will never run automatically. It will only run if it is
    specifically instructed, either by ignoring the trigger or adding it
    as a flow run's start task.
    """

    return False


def all_successful(upstream_states: Dict["Task", "State"]) -> bool:
    """
    Runs if all upstream tasks were successful. SKIPPED tasks are considered
    successes (SKIP_DOWNSTREAM is not).

    If any tasks failed, this task will fail since the trigger can not be
    acheived.
    """

    if not all(s.is_successful() for s in upstream_states.values()):
        raise signals.FAIL("Trigger failed: some preceding tasks failed")
    return True


def all_failed(upstream_states: Dict["Task", "State"]) -> bool:
    """
    Runs if all upstream tasks failed. SKIPPED tasks are considered successes.
    """

    if not all(s.is_failed() for s in upstream_states.values()):
        raise signals.Fail("Trigger failed: some preceding tasks succeeded")
    return True


def all_finished(upstream_states: Dict["Task", "State"]) -> bool:
    """
    Runs if all tasks finished (either SUCCESS, FAIL, SKIP)
    """
    return True


def any_successful(upstream_states: Dict["Task", "State"]) -> bool:
    """
    Runs if any tasks were successful. SKIPPED tasks are considered successes;
    SKIP_DOWNSTREAM is not.
    """

    if not any(s.is_successful() for s in upstream_states.values()):
        raise signals.FAIL("Trigger failed: no preceding tasks succeeded")
    return True


def any_failed(upstream_states: Dict["Task", "State"]) -> bool:
    """
    No failed tasks -> fail
    * skipped tasks count as successes
    """

    if not any(s.is_failed() for s in upstream_states.values()):
        raise signals.FAIL("Trigger failed: no preceding tasks failed")
    return True
