"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""
from prefect import signals
from prefect.utilities.json import serializable


@serializable
def always_run(upstream_states):
    """
    This task will run no matter what the upstream states are.
    """

    return True


@serializable
def manual_only(upstream_states):
    """
    This task will never run automatically. It will only run if it is
    specifically instructed, either by ignoring the trigger or adding it
    as a flow run's start task.
    """

    return False


@serializable
def all_successful(upstream_states):
    """
    Runs if all upstream tasks were successful. SKIPPED tasks are considered
    successes (SKIP_DOWNSTREAM is not).

    If any tasks failed, this task will fail since the trigger can not be
    acheived.
    """

    if not all(s.is_successful() for s in upstream_states.values()):
        raise signals.FAIL("Trigger failed: some preceding tasks failed")
    return True


@serializable
def all_failed(upstream_states):
    """
    Runs if all upstream tasks failed. SKIPPED tasks are considered successes.
    """

    if not all(s.is_failed() for s in upstream_states.values()):
        raise signals.Fail("Trigger failed: some preceding tasks succeeded")
    return True


@serializable
def all_finished(upstream_states):
    """
    Runs if all tasks finished (either SUCCESS, FAIL, SKIP, or SKIP_DOWNSTREAM)
    """

    if not all(s.is_finished() for s in upstream_states.values()):
        raise signals.FAIL(
            "Trigger failed: some preceding tasks did not finish. "
            "(This shouldn't happen!)"
        )
    return True


@serializable
def any_successful(upstream_states):
    """
    Runs if any tasks were successful. SKIPPED tasks are considered successes;
    SKIP_DOWNSTREAM is not.
    """

    if not any(s.is_successful() for s in upstream_states.values()):
        raise signals.FAIL("Trigger failed: no preceding tasks succeeded")
    return True


@serializable
def any_failed(upstream_states):
    """
    No failed tasks -> fail
    * skipped tasks count as successes
    """

    if not any(s.is_failed() for s in upstream_states.values()):
        raise signals.FAIL("Trigger failed: no preceding tasks failed")
    return True
