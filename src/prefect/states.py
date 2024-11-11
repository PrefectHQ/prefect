import asyncio
import datetime
import sys
import traceback
import warnings
from collections import Counter
from types import GeneratorType, TracebackType
from typing import Any, Dict, Iterable, Optional, Type

import anyio
import httpx
import pendulum
from typing_extensions import TypeGuard

from prefect._internal.compatibility import deprecated
from prefect.client.schemas import State as State
from prefect.client.schemas import StateDetails, StateType
from prefect.exceptions import (
    CancelledRun,
    CrashedRun,
    FailedRun,
    MissingContextError,
    MissingResult,
    PausedRun,
    TerminationSignal,
    UnfinishedRun,
)
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.results import (
    BaseResult,
    R,
    ResultRecord,
    ResultRecordMetadata,
    ResultStore,
)
from prefect.utilities.annotations import BaseAnnotation
from prefect.utilities.asyncutils import in_async_main_thread, sync_compatible
from prefect.utilities.collections import ensure_iterable

logger = get_logger("states")


@deprecated.deprecated_parameter(
    "fetch",
    when=lambda fetch: fetch is not True,
    start_date="Oct 2024",
    end_date="Jan 2025",
    help="Please ensure you are awaiting the call to `result()` when calling in an async context.",
)
def get_state_result(
    state: State[R],
    raise_on_failure: bool = True,
    fetch: bool = True,
    retry_result_failure: bool = True,
) -> R:
    """
    Get the result from a state.

    See `State.result()`
    """

    if not fetch and in_async_main_thread():
        warnings.warn(
            (
                "State.result() was called from an async context but not awaited. "
                "This method will be updated to return a coroutine by default in "
                "the future. Pass `fetch=True` and `await` the call to get rid of "
                "this warning."
            ),
            DeprecationWarning,
            stacklevel=2,
        )

        return state.data
    else:
        return _get_state_result(
            state,
            raise_on_failure=raise_on_failure,
            retry_result_failure=retry_result_failure,
        )


RESULT_READ_MAXIMUM_ATTEMPTS = 10
RESULT_READ_RETRY_DELAY = 0.25


async def _get_state_result_data_with_retries(
    state: State[R], retry_result_failure: bool = True
) -> R:
    # Results may be written asynchronously, possibly after their corresponding
    # state has been written and events have been emitted, so we should give some
    # grace here about missing results.  The exception below could come in the form
    # of a missing file, a short read, or other types of errors depending on the
    # result storage backend.
    if retry_result_failure is False:
        max_attempts = 1
    else:
        max_attempts = RESULT_READ_MAXIMUM_ATTEMPTS

    for i in range(1, max_attempts + 1):
        try:
            if isinstance(state.data, ResultRecordMetadata):
                record = await ResultRecord._from_metadata(state.data)
                return record.result
            else:
                return await state.data.get()
        except Exception as e:
            if i == max_attempts:
                raise
            logger.debug(
                "Exception %r while reading result, retry %s/%s in %ss...",
                e,
                i,
                max_attempts,
                RESULT_READ_RETRY_DELAY,
            )
            await asyncio.sleep(RESULT_READ_RETRY_DELAY)


@sync_compatible
async def _get_state_result(
    state: State[R], raise_on_failure: bool, retry_result_failure: bool = True
) -> R:
    """
    Internal implementation for `get_state_result` without async backwards compatibility
    """
    if state.is_paused():
        # Paused states are not truly terminal and do not have results associated with them
        raise PausedRun("Run is paused, its result is not available.", state=state)

    if not state.is_final():
        raise UnfinishedRun(
            f"Run is in {state.type.name} state, its result is not available."
        )

    if raise_on_failure and (
        state.is_crashed() or state.is_failed() or state.is_cancelled()
    ):
        raise await get_state_exception(state)

    if isinstance(state.data, (BaseResult, ResultRecordMetadata)):
        result = await _get_state_result_data_with_retries(
            state, retry_result_failure=retry_result_failure
        )
    elif isinstance(state.data, ResultRecord):
        result = state.data.result

    elif state.data is None:
        if state.is_failed() or state.is_crashed() or state.is_cancelled():
            return await get_state_exception(state)
        else:
            raise MissingResult(
                "State data is missing. "
                "Typically, this occurs when result persistence is disabled and the "
                "state has been retrieved from the API."
            )

    else:
        # The result is attached directly
        result = state.data

    return result


def format_exception(exc: BaseException, tb: TracebackType = None) -> str:
    exc_type = type(exc)
    if tb is not None:
        formatted = "".join(list(traceback.format_exception(exc_type, exc, tb=tb)))
    else:
        formatted = f"{exc_type.__name__}: {exc}"

    # Trim `prefect` module paths from our exception types
    if exc_type.__module__.startswith("prefect."):
        formatted = formatted.replace(
            f"{exc_type.__module__}.{exc_type.__name__}", exc_type.__name__
        )

    return formatted


async def exception_to_crashed_state(
    exc: BaseException,
    result_store: Optional[ResultStore] = None,
) -> State:
    """
    Takes an exception that occurs _outside_ of user code and converts it to a
    'Crash' exception with a 'Crashed' state.
    """
    state_message = None

    if isinstance(exc, anyio.get_cancelled_exc_class()):
        state_message = "Execution was cancelled by the runtime environment."

    elif isinstance(exc, KeyboardInterrupt):
        state_message = "Execution was aborted by an interrupt signal."

    elif isinstance(exc, TerminationSignal):
        state_message = "Execution was aborted by a termination signal."

    elif isinstance(exc, SystemExit):
        state_message = "Execution was aborted by Python system exit call."

    elif isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        try:
            request: httpx.Request = exc.request
        except RuntimeError:
            # The request property is not set
            state_message = (
                "Request failed while attempting to contact the server:"
                f" {format_exception(exc)}"
            )
        else:
            # TODO: We can check if this is actually our API url
            state_message = f"Request to {request.url} failed: {format_exception(exc)}."

    else:
        state_message = (
            "Execution was interrupted by an unexpected exception:"
            f" {format_exception(exc)}"
        )

    if result_store:
        data = result_store.create_result_record(exc)
    else:
        # Attach the exception for local usage, will not be available when retrieved
        # from the API
        data = exc

    return Crashed(message=state_message, data=data)


async def exception_to_failed_state(
    exc: Optional[BaseException] = None,
    result_store: Optional[ResultStore] = None,
    write_result: bool = False,
    **kwargs,
) -> State:
    """
    Convenience function for creating `Failed` states from exceptions
    """
    try:
        local_logger = get_run_logger()
    except MissingContextError:
        local_logger = logger

    if not exc:
        _, exc, _ = sys.exc_info()
        if exc is None:
            raise ValueError(
                "Exception was not passed and no active exception could be found."
            )
    else:
        pass

    if result_store:
        data = result_store.create_result_record(exc)
        if write_result:
            try:
                await result_store.apersist_result_record(data)
            except Exception as nested_exc:
                local_logger.warning(
                    "Failed to write result: %s Execution will continue, but the result has not been written",
                    nested_exc,
                )
    else:
        # Attach the exception for local usage, will not be available when retrieved
        # from the API
        data = exc

    existing_message = kwargs.pop("message", "")
    if existing_message and not existing_message.endswith(" "):
        existing_message += " "

    # TODO: Consider if we want to include traceback information, it is intentionally
    #       excluded from messages for now
    message = existing_message + format_exception(exc)

    state = Failed(data=data, message=message, **kwargs)
    state.state_details.retriable = False

    return state


async def return_value_to_state(
    retval: R,
    result_store: ResultStore,
    key: Optional[str] = None,
    expiration: Optional[datetime.datetime] = None,
    write_result: bool = False,
) -> State[R]:
    """
    Given a return value from a user's function, create a `State` the run should
    be placed in.

    - If data is returned, we create a 'COMPLETED' state with the data
    - If a single, manually created state is returned, we use that state as given
        (manual creation is determined by the lack of ids)
    - If an upstream state or iterable of upstream states is returned, we apply the
        aggregate rule

    The aggregate rule says that given multiple states we will determine the final state
    such that:

    - If any states are not COMPLETED the final state is FAILED
    - If all of the states are COMPLETED the final state is COMPLETED
    - The states will be placed in the final state `data` attribute

    Callers should resolve all futures into states before passing return values to this
    function.
    """
    try:
        local_logger = get_run_logger()
    except MissingContextError:
        local_logger = logger

    if (
        isinstance(retval, State)
        # Check for manual creation
        and not retval.state_details.flow_run_id
        and not retval.state_details.task_run_id
    ):
        state = retval
        # Unless the user has already constructed a result explicitly, use the store
        # to update the data to the correct type
        if not isinstance(state.data, (BaseResult, ResultRecord, ResultRecordMetadata)):
            result_record = result_store.create_result_record(
                state.data,
                key=key,
                expiration=expiration,
            )
            if write_result:
                try:
                    await result_store.apersist_result_record(result_record)
                except Exception as exc:
                    local_logger.warning(
                        "Encountered an error while persisting result: %s Execution will continue, but the result has not been persisted",
                        exc,
                    )
            state.data = result_record
        return state

    # Determine a new state from the aggregate of contained states
    if isinstance(retval, State) or is_state_iterable(retval):
        states = StateGroup(ensure_iterable(retval))

        # Determine the new state type
        if states.all_completed():
            new_state_type = StateType.COMPLETED
        elif states.any_cancelled():
            new_state_type = StateType.CANCELLED
        elif states.any_paused():
            new_state_type = StateType.PAUSED
        else:
            new_state_type = StateType.FAILED

        # Generate a nice message for the aggregate
        if states.all_completed():
            message = "All states completed."
        elif states.any_cancelled():
            message = f"{states.cancelled_count}/{states.total_count} states cancelled."
        elif states.any_paused():
            message = f"{states.paused_count}/{states.total_count} states paused."
        elif states.any_failed():
            message = f"{states.fail_count}/{states.total_count} states failed."
        elif not states.all_final():
            message = (
                f"{states.not_final_count}/{states.total_count} states are not final."
            )
        else:
            message = "Given states: " + states.counts_message()

        # TODO: We may actually want to set the data to a `StateGroup` object and just
        #       allow it to be unpacked into a tuple and such so users can interact with
        #       it
        result_record = result_store.create_result_record(
            retval,
            key=key,
            expiration=expiration,
        )
        if write_result:
            try:
                await result_store.apersist_result_record(result_record)
            except Exception as exc:
                local_logger.warning(
                    "Encountered an error while persisting result: %s Execution will continue, but the result has not been persisted",
                    exc,
                )
        return State(
            type=new_state_type,
            message=message,
            data=result_record,
        )

    # Generators aren't portable, implicitly convert them to a list.
    if isinstance(retval, GeneratorType):
        data = list(retval)
    else:
        data = retval

    # Otherwise, they just gave data and this is a completed retval
    if isinstance(data, (BaseResult, ResultRecord)):
        return Completed(data=data)
    else:
        result_record = result_store.create_result_record(
            data,
            key=key,
            expiration=expiration,
        )
        if write_result:
            try:
                await result_store.apersist_result_record(result_record)
            except Exception as exc:
                local_logger.warning(
                    "Encountered an error while persisting result: %s Execution will continue, but the result has not been persisted",
                    exc,
                )
        return Completed(data=result_record)


@sync_compatible
async def get_state_exception(state: State) -> BaseException:
    """
    If not given a FAILED or CRASHED state, this raise a value error.

    If the state result is a state, its exception will be returned.

    If the state result is an iterable of states, the exception of the first failure
    will be returned.

    If the state result is a string, a wrapper exception will be returned with the
    string as the message.

    If the state result is null, a wrapper exception will be returned with the state
    message attached.

    If the state result is not of a known type, a `TypeError` will be returned.

    When a wrapper exception is returned, the type will be:
        - `FailedRun` if the state type is FAILED.
        - `CrashedRun` if the state type is CRASHED.
        - `CancelledRun` if the state type is CANCELLED.
    """

    if state.is_failed():
        wrapper = FailedRun
        default_message = "Run failed."
    elif state.is_crashed():
        wrapper = CrashedRun
        default_message = "Run crashed."
    elif state.is_cancelled():
        wrapper = CancelledRun
        default_message = "Run cancelled."
    else:
        raise ValueError(f"Expected failed or crashed state got {state!r}.")

    if isinstance(state.data, BaseResult):
        result = await _get_state_result_data_with_retries(state)
    elif isinstance(state.data, ResultRecord):
        result = state.data.result
    elif isinstance(state.data, ResultRecordMetadata):
        record = await ResultRecord._from_metadata(state.data)
        result = record.result
    elif state.data is None:
        result = None
    else:
        result = state.data

    if result is None:
        return wrapper(state.message or default_message)

    if isinstance(result, Exception):
        return result

    elif isinstance(result, BaseException):
        return result

    elif isinstance(result, str):
        return wrapper(result)

    elif isinstance(result, State):
        # Return the exception from the inner state
        return await get_state_exception(result)

    elif is_state_iterable(result):
        # Return the first failure
        for state in result:
            if state.is_failed() or state.is_crashed() or state.is_cancelled():
                return await get_state_exception(state)

        raise ValueError(
            "Failed state result was an iterable of states but none were failed."
        )

    else:
        raise TypeError(
            f"Unexpected result for failed state: {result!r} —— "
            f"{type(result).__name__} cannot be resolved into an exception"
        )


@sync_compatible
async def raise_state_exception(state: State) -> None:
    """
    Given a FAILED or CRASHED state, raise the contained exception.
    """
    if not (state.is_failed() or state.is_crashed() or state.is_cancelled()):
        return None

    raise await get_state_exception(state)


def is_state_iterable(obj: Any) -> TypeGuard[Iterable[State]]:
    """
    Check if a the given object is an iterable of states types

    Supported iterables are:
    - set
    - list
    - tuple

    Other iterables will return `False` even if they contain states.
    """
    # We do not check for arbitrary iterables because this is not intended to be used
    # for things like dictionaries, dataframes, or pydantic models
    if (
        not isinstance(obj, BaseAnnotation)
        and isinstance(obj, (list, set, tuple))
        and obj
    ):
        return all([isinstance(o, State) for o in obj])
    else:
        return False


class StateGroup:
    def __init__(self, states: Iterable[State]) -> None:
        self.states = states
        self.type_counts = self._get_type_counts(states)
        self.total_count = len(states)
        self.cancelled_count = self.type_counts[StateType.CANCELLED]
        self.final_count = sum(state.is_final() for state in states)
        self.not_final_count = self.total_count - self.final_count
        self.paused_count = self.type_counts[StateType.PAUSED]

    @property
    def fail_count(self):
        return self.type_counts[StateType.FAILED] + self.type_counts[StateType.CRASHED]

    def all_completed(self) -> bool:
        return self.type_counts[StateType.COMPLETED] == self.total_count

    def any_cancelled(self) -> bool:
        return self.cancelled_count > 0

    def any_failed(self) -> bool:
        return (
            self.type_counts[StateType.FAILED] > 0
            or self.type_counts[StateType.CRASHED] > 0
        )

    def any_paused(self) -> bool:
        return self.paused_count > 0

    def all_final(self) -> bool:
        return self.final_count == self.total_count

    def counts_message(self) -> str:
        count_messages = [f"total={self.total_count}"]
        if self.not_final_count:
            count_messages.append(f"not_final={self.not_final_count}")

        count_messages += [
            f"{state_type.value!r}={count}"
            for state_type, count in self.type_counts.items()
            if count
        ]

        return ", ".join(count_messages)

    @staticmethod
    def _get_type_counts(states: Iterable[State]) -> Dict[StateType, int]:
        return Counter(state.type for state in states)

    def __repr__(self) -> str:
        return f"StateGroup<{self.counts_message()}>"


def Scheduled(
    cls: Type[State[R]] = State,
    scheduled_time: Optional[datetime.datetime] = None,
    **kwargs: Any,
) -> State[R]:
    """Convenience function for creating `Scheduled` states.

    Returns:
        State: a Scheduled state
    """
    state_details = StateDetails.model_validate(kwargs.pop("state_details", {}))
    if scheduled_time is None:
        scheduled_time = pendulum.now("UTC")
    elif state_details.scheduled_time:
        raise ValueError("An extra scheduled_time was provided in state_details")
    state_details.scheduled_time = scheduled_time

    return cls(type=StateType.SCHEDULED, state_details=state_details, **kwargs)


def Completed(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Completed` states.

    Returns:
        State: a Completed state
    """
    return cls(type=StateType.COMPLETED, **kwargs)


def Running(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Running` states.

    Returns:
        State: a Running state
    """
    return cls(type=StateType.RUNNING, **kwargs)


def Failed(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Failed` states.

    Returns:
        State: a Failed state
    """
    return cls(type=StateType.FAILED, **kwargs)


def Crashed(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Crashed` states.

    Returns:
        State: a Crashed state
    """
    return cls(type=StateType.CRASHED, **kwargs)


def Cancelling(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Cancelling` states.

    Returns:
        State: a Cancelling state
    """
    return cls(type=StateType.CANCELLING, **kwargs)


def Cancelled(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Cancelled` states.

    Returns:
        State: a Cancelled state
    """
    return cls(type=StateType.CANCELLED, **kwargs)


def Pending(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Pending` states.

    Returns:
        State: a Pending state
    """
    return cls(type=StateType.PENDING, **kwargs)


def Paused(
    cls: Type[State[R]] = State,
    timeout_seconds: Optional[int] = None,
    pause_expiration_time: Optional[datetime.datetime] = None,
    reschedule: bool = False,
    pause_key: Optional[str] = None,
    **kwargs: Any,
) -> State[R]:
    """Convenience function for creating `Paused` states.

    Returns:
        State: a Paused state
    """
    state_details = StateDetails.model_validate(kwargs.pop("state_details", {}))

    if state_details.pause_timeout:
        raise ValueError("An extra pause timeout was provided in state_details")

    if pause_expiration_time is not None and timeout_seconds is not None:
        raise ValueError(
            "Cannot supply both a pause_expiration_time and timeout_seconds"
        )

    if pause_expiration_time is None and timeout_seconds is None:
        pass
    else:
        state_details.pause_timeout = pause_expiration_time or (
            pendulum.now("UTC") + pendulum.Duration(seconds=timeout_seconds)
        )

    state_details.pause_reschedule = reschedule
    state_details.pause_key = pause_key

    return cls(type=StateType.PAUSED, state_details=state_details, **kwargs)


def Suspended(
    cls: Type[State[R]] = State,
    timeout_seconds: Optional[int] = None,
    pause_expiration_time: Optional[datetime.datetime] = None,
    pause_key: Optional[str] = None,
    **kwargs: Any,
):
    """Convenience function for creating `Suspended` states.

    Returns:
        State: a Suspended state
    """
    return Paused(
        cls=cls,
        name="Suspended",
        reschedule=True,
        timeout_seconds=timeout_seconds,
        pause_expiration_time=pause_expiration_time,
        pause_key=pause_key,
        **kwargs,
    )


def AwaitingRetry(
    cls: Type[State[R]] = State,
    scheduled_time: Optional[datetime.datetime] = None,
    **kwargs: Any,
) -> State[R]:
    """Convenience function for creating `AwaitingRetry` states.

    Returns:
        State: a AwaitingRetry state
    """
    return Scheduled(
        cls=cls, scheduled_time=scheduled_time, name="AwaitingRetry", **kwargs
    )


def AwaitingConcurrencySlot(
    cls: Type[State[R]] = State,
    scheduled_time: Optional[datetime.datetime] = None,
    **kwargs: Any,
) -> State[R]:
    """Convenience function for creating `AwaitingConcurrencySlot` states.

    Returns:
        State: a AwaitingConcurrencySlot state
    """
    return Scheduled(
        cls=cls, scheduled_time=scheduled_time, name="AwaitingConcurrencySlot", **kwargs
    )


def Retrying(cls: Type[State[R]] = State, **kwargs: Any) -> State[R]:
    """Convenience function for creating `Retrying` states.

    Returns:
        State: a Retrying state
    """
    return cls(type=StateType.RUNNING, name="Retrying", **kwargs)


def Late(
    cls: Type[State[R]] = State,
    scheduled_time: Optional[datetime.datetime] = None,
    **kwargs: Any,
) -> State[R]:
    """Convenience function for creating `Late` states.

    Returns:
        State: a Late state
    """
    return Scheduled(cls=cls, scheduled_time=scheduled_time, name="Late", **kwargs)
