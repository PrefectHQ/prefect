"""
Triggers are functions that determine if task state should change based on
the state of preceding tasks.
"""
from prefect import signals
from prefect.utilities.serialize import JSONSerializable


def autoinstantiate(cls):
    """
    Decorator to automatically instantiate a class
    """
    return cls()


class Trigger(JSONSerializable):
    pass

    @staticmethod
    def __call__(upstream_states):
        raise NotImplementedError()


@autoinstantiate
class AlwaysRun(Trigger):
    """
    This task will run no matter what the upstream states are.
    """

    @staticmethod
    def __call__(upstream_states):
        return True


@autoinstantiate
class ManualOnly(Trigger):
    """
    This task will never run automatically. It will only run if it is
    specifically instructed, either by ignoring the trigger or adding it
    as a flow run's start task.
    """

    @staticmethod
    def __call__(upstream_states):
        return False


@autoinstantiate
class AllSuccessful(Trigger):
    """
    Runs if all upstream tasks were successful. SKIPPED tasks are considered
    successes (SKIP_DOWNSTREAM is not).

    If any tasks failed, this task will fail since the trigger can not be
    acheived.
    """

    @staticmethod
    def __call__(upstream_states):
        if not all(s.is_successful() for s in upstream_states.values()):
            raise signals.FAIL('Trigger failed: some preceding tasks failed')
        return True


@autoinstantiate
class AllFailed(Trigger):
    """
    Runs if all upstream tasks failed. SKIPPED tasks are considered successes.
    """

    @staticmethod
    def __call__(upstream_states):
        if not all(s.is_failed() for s in upstream_states.values()):
            raise signals.Fail('Trigger failed: some preceding tasks succeeded')
        return True


@autoinstantiate
class AllFinished(Trigger):
    """
    Runs if all tasks finished (either SUCCESS, FAIL, SKIP, or SKIP_DOWNSTREAM)
    """

    @staticmethod
    def __call__(upstream_states):
        if not all(s.is_finished() for s in upstream_states.values()):
            raise signals.FAIL(
                "Trigger failed: some preceding tasks did not finish. "
                "(This shouldn't happen!)")
        return True


@autoinstantiate
class AnySuccessful(Trigger):
    """
    Runs if any tasks were successful. SKIPPED tasks are considered successes;
    SKIP_DOWNSTREAM is not.
    """

    @staticmethod
    def __call__(upstream_states):
        if not any(s.is_successful() for s in upstream_states.values()):
            raise signals.FAIL('Trigger failed: no preceding tasks succeeded')
        return True


@autoinstantiate
class AnyFailed(Trigger):
    """
    No failed tasks -> fail
    * skipped tasks count as successes
    """

    @staticmethod
    def __call__(upstream_states):
        if not any(s.is_failed() for s in upstream_states.values()):
            raise signals.FAIL('Trigger failed: no preceding tasks failed')
        return True
