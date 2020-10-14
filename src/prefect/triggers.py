"""
Triggers are functions that determine if a task should run based on
the state of upstream tasks.

For example, suppose we want to construct a flow with one root task; if this task
succeeds, we want to run task B.  If instead it fails, we want to run task C.  We
can accomplish this pattern through the use of triggers:

```python
import random

from prefect.triggers import all_successful, all_failed
from prefect import task, Flow


@task(name="Task A")
def task_a():
    if random.random() > 0.5:
        raise ValueError("Non-deterministic error has occured.")

@task(name="Task B", trigger=all_successful)
def task_b():
    # do something interesting
    pass

@task(name="Task C", trigger=all_failed)
def task_c():
    # do something interesting
    pass


with Flow("Trigger example") as flow:
    success = task_b(upstream_tasks=[task_a])
    fail = task_c(upstream_tasks=[task_a])

## note that as written, this flow will fail regardless of the path taken
## because *at least one* terminal task will fail;
## to fix this, we want to set Task B as the "reference task" for the Flow
## so that its state uniquely determines the overall Flow state
flow.set_reference_tasks([success])

flow.run()
```
"""
from typing import TYPE_CHECKING, Callable, Dict, Union

from prefect import context
from prefect.engine import signals
from prefect.engine.state import Mapped

if TYPE_CHECKING:
    from prefect.engine import state  # noqa
    from prefect import core  # noqa


def _get_all_states_as_set(upstream_states: Dict["core.Edge", "state.State"]) -> set:
    """
    Convert all upstream states to a set and expand map states.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states

    Returns:
        - set: a set of all upstream State objects
    """
    all_states = set()
    for upstream_state in upstream_states.values():
        if isinstance(upstream_state, Mapped):
            all_states.update(upstream_state.map_states)
        else:
            all_states.add(upstream_state)
    return all_states


def all_finished(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    This task will run no matter what the upstream states are, as long as they are finished.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """
    if not all(s.is_finished() for s in _get_all_states_as_set(upstream_states)):
        raise signals.TRIGGERFAIL(
            'Trigger was "all_finished" but some of the upstream tasks were not finished.'
        )

    return True


def manual_only(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    This task will never run automatically, because this trigger will
    always place the task in a Paused state. The only exception is if
    the "resume" keyword is found in the Prefect context, which happens
    automatically when a task starts in a Resume state.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """
    if context.get("resume"):
        return True

    raise signals.PAUSE('Trigger function is "manual_only"')


def all_successful(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    Runs if all upstream tasks were successful. Note that `SKIPPED` tasks are considered
    successes and `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """

    if not all(s.is_successful() for s in _get_all_states_as_set(upstream_states)):
        raise signals.TRIGGERFAIL(
            'Trigger was "all_successful" but some of the upstream tasks failed.'
        )
    return True


def all_failed(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    Runs if all upstream tasks failed. Note that `SKIPPED` tasks are considered successes
    and `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """

    if not all(s.is_failed() for s in _get_all_states_as_set(upstream_states)):
        raise signals.TRIGGERFAIL(
            'Trigger was "all_failed" but some of the upstream tasks succeeded.'
        )
    return True


def any_successful(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    Runs if any tasks were successful. Note that `SKIPPED` tasks are considered successes
    and `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """

    if upstream_states and not any(
        s.is_successful() for s in _get_all_states_as_set(upstream_states)
    ):
        raise signals.TRIGGERFAIL(
            'Trigger was "any_successful" but none of the upstream tasks succeeded.'
        )
    return True


def any_failed(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    Runs if any tasks failed. Note that `SKIPPED` tasks are considered successes and
    `TRIGGER_FAILED` tasks are considered failures.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """

    if upstream_states and not any(
        s.is_failed() for s in _get_all_states_as_set(upstream_states)
    ):
        raise signals.TRIGGERFAIL(
            'Trigger was "any_failed" but none of the upstream tasks failed.'
        )
    return True


def some_failed(
    at_least: Union[int, float] = None, at_most: Union[int, float] = None
) -> Callable[[Dict["core.Edge", "state.State"]], bool]:
    """
    Runs if some amount of upstream tasks failed. This amount can be specified
    as an upper bound (`at_most`) or a lower bound (`at_least`), and can be
    provided as an absolute number or a percentage of upstream tasks.

    Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED`
    tasks are considered failures.

    Args:
        - at_least (Union[int, float], optional): the minimum number of
            upstream failures that must occur for this task to run.  If the
            provided number is less than 1, it will be interpreted as a
            percentage, otherwise as an absolute number.
        - at_most (Union[int, float], optional): the maximum number of upstream
           failures to allow for this task to run.  If the provided number is
           less than 1, it will be interpreted as a percentage, otherwise as an
           absolute number."""

    def _some_failed(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
        """
        The underlying trigger function.

        Args:
            - upstream_states (dict[Edge, State]): the set of all upstream states

        Returns:
            - bool: whether the trigger thresolds were met
        """
        if not upstream_states:
            return True

        # scale conversions
        num_failed = len(
            [s for s in _get_all_states_as_set(upstream_states) if s.is_failed()]
        )
        num_states = len(_get_all_states_as_set(upstream_states))
        if at_least is not None:
            min_num = (num_states * at_least) if at_least < 1 else at_least
        else:
            min_num = 0
        if at_most is not None:
            max_num = (num_states * at_most) if at_most < 1 else at_most
        else:
            max_num = num_states

        if not (min_num <= num_failed <= max_num):
            raise signals.TRIGGERFAIL(
                'Trigger was "some_failed" but thresholds were not met.'
            )
        return True

    return _some_failed


def some_successful(
    at_least: Union[int, float] = None, at_most: Union[int, float] = None
) -> Callable[[Dict["core.Edge", "state.State"]], bool]:
    """

    Runs if some amount of upstream tasks succeed. This amount can be specified
    as an upper bound (`at_most`) or a lower bound (`at_least`), and can be
    provided as an absolute number or a percentage of upstream tasks.

    Note that `SKIPPED` tasks are considered successes and `TRIGGER_FAILED`
    tasks are considered failures.

    Args:
        - at_least (Union[int, float], optional): the minimum number of
            upstream successes that must occur for this task to run.  If the
            provided number is less than 1, it will be interpreted as a
            percentage, otherwise as an absolute number.
        - at_most (Union[int, float], optional): the maximum number of upstream
            successes to allow for this task to run.  If the provided number is
            less than 1, it will be interpreted as a percentage, otherwise as
            an absolute number.
    """

    def _some_successful(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
        """
        The underlying trigger function.

        Args:
            - upstream_states (dict[Edge, State]): the set of all upstream states

        Returns:
            - bool: whether the trigger thresolds were met
        """
        if not upstream_states:
            return True

        # scale conversions
        num_success = len(
            [s for s in _get_all_states_as_set(upstream_states) if s.is_successful()]
        )
        num_states = len(_get_all_states_as_set(upstream_states))
        if at_least is not None:
            min_num = (num_states * at_least) if at_least < 1 else at_least
        else:
            min_num = 0
        if at_most is not None:
            max_num = (num_states * at_most) if at_most < 1 else at_most
        else:
            max_num = num_states

        if not (min_num <= num_success <= max_num):
            raise signals.TRIGGERFAIL(
                'Trigger was "some_successful" but thresholds were not met.'
            )
        return True

    return _some_successful


def not_all_skipped(upstream_states: Dict["core.Edge", "state.State"]) -> bool:
    """
    Runs if all upstream tasks were successful and were not all skipped.

    Args:
        - upstream_states (dict[Edge, State]): the set of all upstream states
    """

    if all(state.is_skipped() for state in _get_all_states_as_set(upstream_states)):
        raise signals.SKIP("All upstreams were skipped", result=None)
    elif not all(
        state.is_successful() for state in _get_all_states_as_set(upstream_states)
    ):
        raise signals.TRIGGERFAIL(
            'Trigger was "not_all_skipped" but some of the upstream tasks failed.'
        )
    return True


# aliases
always_run = all_finished  # type: Callable[[Dict["core.Edge", "state.State"]], bool]
