# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
State is the main currency in the Prefect platform. It is used to represent the current
status of a flow or task.

This module contains all Prefect state classes, all ultimately inheriting from the base State class as follows:

![](/state_inheritance_diagram.svg) {style="text-align: center;"}

Every run is initialized with the `Pending` state, meaning that it is waiting for
execution. During execution a run will enter a `Running` state. Finally, runs become `Finished`.
"""
import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

import pendulum

import prefect
from prefect.engine.result_serializers import ResultSerializer
from prefect.utilities.collections import DotDict
from prefect.utilities.datetimes import ensure_tz_aware


class StateMetaData(DotDict):
    def __init__(self) -> None:
        init_dict = {
            "result": {"raw": True},
            "cached_inputs": defaultdict(lambda: {"raw": True}),
        }
        super().__init__(init_dict)


class State:
    """
    Base state class implementing the basic helper methods for checking state.

    **Note:** Each state-checking method (e.g., `is_failed()`) will also return `True`
    for all _subclasses_ of the parent state.  So, for example:
    ```python
    my_state = TriggerFailed()
    my_state.is_failed() # returns True

    another_state = Retrying()
    another_state.is_pending() # returns True
    ```

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#000000"

    def __init__(self, message: str = None, result: Any = None):
        self.message = message
        self.result = result
        self._metadata = StateMetaData()

    def __repr__(self) -> str:
        if self.message:
            return '{}("{}")'.format(type(self).__name__, self.message)
        else:
            return "{}()".format(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        """
        Equality depends on state type and data, but not message
        """
        if type(self) == type(other):
            assert isinstance(other, State)  # this assertion is here for MyPy only
            eq = True
            for attr in self.__dict__:
                if attr.startswith("_") or attr == "message":
                    continue
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False

    def __hash__(self) -> int:
        return id(self)

    def update_input_metadata(self, input_handlers: dict) -> None:
        """
        Updates the `cached_inputs` metadata entry of this state with all appropriate result handlers.

        Args:
            - input_handlers (dict): the individual serialized result handlers to use when
                processing each variable in `cached_inputs`

        Modifies the state object in place.
        """
        for variable in self.cached_inputs or {}:  # type: ignore
            self._metadata["cached_inputs"][variable][
                "result_serializer"
            ] = input_handlers[variable]

    def handle_inputs(self) -> None:
        """
        Handles the `cached_inputs` attribute of this state (if it has one).

        Modifies the state object in place.
        """
        from prefect.serialization.result_serializers import ResultSerializerSchema

        schema = ResultSerializerSchema()
        input_handlers = {
            var: schema.load(self._metadata["cached_inputs"][var]["result_serializer"])
            for var in (self.cached_inputs or {})  # type: ignore
        }

        for variable in self.cached_inputs:  # type: ignore
            var_info = self._metadata["cached_inputs"][variable]
            if var_info["raw"] is True:
                packed_value = input_handlers[variable].serialize(
                    self.cached_inputs[variable]  # type: ignore
                )
                self.cached_inputs[variable] = packed_value  # type: ignore
                self._metadata["cached_inputs"][variable]["raw"] = False

    def update_output_metadata(self, result_serializer: ResultSerializer) -> None:
        """
        Handles the `cached_result` attribute of this state (if it has one).

        Args:
            - result_serializer (ResultSerializer): the result handler to use when
                processing the `cached_result`

        Modifies the state object in place.
        """
        from prefect.serialization.result_serializers import ResultSerializerSchema

        schema = ResultSerializerSchema()
        self._metadata["result"]["result_serializer"] = schema.dump(result_serializer)

    def handle_outputs(self) -> None:
        """
        Handles the `cached_result` attribute of this state (if it has one).

        Modifies the state object in place.
        """
        from prefect.serialization.result_serializers import ResultSerializerSchema

        schema = ResultSerializerSchema()
        result_serializer = schema.load(self._metadata["result"]["result_serializer"])

        if self._metadata["result"]["raw"] is True:
            packed_value = result_serializer.serialize(self.result)  # type: ignore
            self.result = packed_value  # type: ignore
            self._metadata["result"]["raw"] = False

    def ensure_raw(self) -> None:
        """
        Ensures that all attributes are _raw_ (as specified in `self._metadata`).

        Modifies the state object in place.
        """
        from prefect.serialization.result_serializers import ResultSerializerSchema

        schema = ResultSerializerSchema()

        if self._metadata["result"].get("raw") is False:
            handler = schema.load(self._metadata["result"]["result_serializer"])
            unpacked_value = handler.deserialize(self.result)
            self.result = unpacked_value
            self._metadata["result"].update(raw=True)

        if getattr(self, "cached_inputs", None) is not None:
            # each variable could presumably come from different tasks with
            # different result handlers
            for variable in self.cached_inputs:  # type: ignore
                var_info = self._metadata["cached_inputs"][variable]
                if var_info["raw"] is False:
                    handler = schema.load(var_info["result_serializer"])
                    unpacked_value = handler.deserialize(
                        self.cached_inputs[variable]  # type: ignore
                    )
                    self.cached_inputs[variable] = unpacked_value  # type: ignore
                    self._metadata["cached_inputs"][variable]["raw"] = True

        if getattr(self, "cached", None) is not None:
            self.cached.ensure_raw()  # type: ignore

    def is_pending(self) -> bool:
        """
        Checks if the object is currently in a pending state

        Returns:
            - bool: `True` if the state is pending, `False` otherwise
        """

        return isinstance(self, Pending)

    def is_running(self) -> bool:
        """
        Checks if the object is currently in a running state

        Returns:
            - bool: `True` if the state is running, `False` otherwise
        """
        return isinstance(self, Running)

    def is_finished(self) -> bool:
        """
        Checks if the object is currently in a finished state

        Returns:
            - bool: `True` if the state is finished, `False` otherwise
        """
        return isinstance(self, Finished)

    def is_scheduled(self) -> bool:
        """
        Checks if the object is currently in a scheduled state, which includes retrying.

        Returns:
            - bool: `True` if the state is skipped, `False` otherwise
        """
        return isinstance(self, Scheduled)

    def is_skipped(self) -> bool:
        """
        Checks if the object is currently in a skipped state

        Returns:
            - bool: `True` if the state is skipped, `False` otherwise
        """
        return isinstance(self, Skipped)

    def is_successful(self) -> bool:
        """
        Checks if the object is currently in a successful state

        Returns:
            - bool: `True` if the state is successful, `False` otherwise
        """
        return isinstance(self, Success)

    def is_failed(self) -> bool:
        """
        Checks if the object is currently in a failed state

        Returns:
            - bool: `True` if the state is failed, `False` otherwise
        """
        return isinstance(self, Failed)

    def is_mapped(self) -> bool:
        """
        Checks if the object is currently in a mapped state

        Returns:
            - bool: `True` if the state is mapped, `False` otherwise
        """
        return isinstance(self, Mapped)

    @staticmethod
    def deserialize(json_blob: dict) -> "State":
        """
        Deserializes the state from a dict.

        Args:
            - json_blob (dict): the JSON representing the serialized state
        """
        from prefect.serialization.state import StateSchema

        state = StateSchema().load(json_blob)
        return state

    def serialize(self) -> dict:
        """
        Serializes the state to a dict.

        Returns:
            - dict: a JSON representation of the state
        """
        from prefect.serialization.state import StateSchema

        json_blob = StateSchema().dump(self)
        return json_blob


# -------------------------------------------------------------------
# Pending States
# -------------------------------------------------------------------


class Pending(State):
    """
    Base Pending state; default state for new tasks.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
    """

    color = "#d3d3d3"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        cached_inputs: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result)
        self.cached_inputs = cached_inputs


class Paused(Pending):
    """
    Paused state for tasks which require manual execution.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
    """

    color = "#800000"


class Scheduled(Pending):
    """
    Pending state indicating the object has been scheduled to run.

    Scheduled states have a `start_time` which indicates when they are scheduled to run.
    Only scheduled states have this property; this is important because non-Python systems
    identify scheduled states by the presence of this property.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to run
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to values.  Used / set if the Task requires Retries.
    """

    color = "#b0c4de"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result, cached_inputs=cached_inputs)
        self.start_time = ensure_tz_aware(start_time or pendulum.now("utc"))


class Submitted(State):
    """
    The `Submitted` state is used to indicate that another state, usually a `Scheduled`
    state, has been handled. For example, if a task is in a `Retrying` state, then at
    the appropriate time it may be put into a `Submitted` state referencing the
    `Retrying` state. This communicates to the system that the retry has been handled,
    without losing the information contained in the `Retry` state.

    The `Submitted` state should be initialized with another state, which it wraps. The
    wrapped state is extracted at the beginning of a task run.

    Args:
        - message (string): a message for the state.
        - result (Any, optional): Defaults to `None`.
        - state (Scheduled): the `Scheduled` state that has been marked as
            "submitted". The message of the `Submitted` state will be taken from this
            `state`.

    """

    def __init__(self, message: str = None, result: Any = None, state: State = None):
        super().__init__(message=message, result=result)
        self.state = state


class Resume(Scheduled):
    """
    Resume state indicating the object can resume execution (presumably from a `Paused` state).

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to run
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to values.  Used / set if the Task requires Retries.
    """

    color = "#20B2AA"


class Retrying(Scheduled):
    """
    Pending state indicating the object has been scheduled to be retried.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - start_time (datetime): time at which the task is scheduled to be retried
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
            keys to values.  Used / set if the Task requires Retries.
        - run_count (int): The number of runs that had been attempted at the time of this
            Retry. Defaults to the value stored in context under "task_run_count" or 1,
            if that value isn't found.
    """

    color = "#FFFF00"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        start_time: datetime.datetime = None,
        cached_inputs: Dict[str, Any] = None,
        run_count: int = None,
    ):
        super().__init__(
            result=result,
            message=message,
            start_time=start_time,
            cached_inputs=cached_inputs,
        )
        if run_count is None:
            run_count = prefect.context.get("task_run_count", 1)
        assert run_count is not None  # mypy assert
        self.run_count = run_count  # type: int


# -------------------------------------------------------------------
# Running States
# -------------------------------------------------------------------


class Running(State):
    """
    Base running state. Indicates that a task is currently running.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#00FF00"


# -------------------------------------------------------------------
# Finished States
# -------------------------------------------------------------------


class Finished(State):
    """
    Base finished state. Indicates when a class has reached some form of completion.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#BA55D3"


class Success(Finished):
    """
    Finished state indicating success.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#008000"


class Cached(Success):
    """
    Cached, which represents a Task whose outputs have been cached.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the
            state, which will be cached.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
        - cached_parameters (dict): Defaults to `None`
        - cached_result_expiration (datetime): The time at which this cache
            expires and can no longer be used. Defaults to `None`
    """

    color = "#ffa500"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        cached_inputs: Dict[str, Any] = None,
        cached_parameters: Dict[str, Any] = None,
        cached_result_expiration: datetime.datetime = None,
    ):
        super().__init__(message=message, result=result)
        self.cached_inputs = cached_inputs
        self.cached_parameters = cached_parameters  # type: Optional[Dict[str, Any]]
        if cached_result_expiration is not None:
            cached_result_expiration = ensure_tz_aware(cached_result_expiration)
        self.cached_result_expiration = (
            cached_result_expiration
        )  # type: Optional[datetime.datetime]


class Mapped(Success):
    """
    State indicated this task was mapped over, and all mapped tasks were _submitted_ successfully.
    Note that this does _not_ imply the individual mapped tasks were successful, just that they
    have been submitted.

    You can not set the `result` of a Mapped state; it is determined by the results of its
    children states.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `[]`. A data payload for the state.
        - children (List): A list containing the states of any "children" of this task. When
            a task enters a Mapped state, it indicates that it has dynamically created copies
            of itself to map its operation over its inputs. Those copies are the children.
    """

    color = "#97FFFF"

    def __init__(
        self, message: str = None, result: Any = None, map_states: List[State] = None
    ):
        super().__init__(message=message, result=result)
        self.map_states = map_states or []  # type: List[State]

    @property
    def n_map_states(self) -> int:
        return len(self.map_states)


class Failed(Finished):
    """
    Finished state indicating failure.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#FF0000"


class TimedOut(Failed):
    """
    Finished state indicating failure due to execution timeout.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
        - cached_inputs (dict): Defaults to `None`. A dictionary of input
        keys to values.  Used / set if the Task requires Retries.
    """

    color = "#CDC9A5"

    def __init__(
        self,
        message: str = None,
        result: Any = None,
        cached_inputs: Dict[str, Any] = None,
    ):
        super().__init__(message=message, result=result)
        self.cached_inputs = cached_inputs


class TriggerFailed(Failed):
    """
    Finished state indicating failure due to trigger.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#F08080"


class Skipped(Success):
    """
    Finished state indicating success on account of being skipped.

    Args:
        - message (str or Exception, optional): Defaults to `None`. A message about the
            state, which could be an `Exception` (or [`Signal`](signals.html)) that caused it.
        - result (Any, optional): Defaults to `None`. A data payload for the state.
    """

    color = "#F0FFF0"

    # note: this does not allow setting "cached" as Success states do
    def __init__(self, message: str = None, result: Any = None):
        super().__init__(message=message, result=result)
