"""
Private module containing sync versions of state functions.

These functions are used internally by the sync task engine to avoid
run_coro_as_sync overhead on Windows.
"""

from __future__ import annotations

import datetime
import sys
import uuid
from types import GeneratorType
from typing import TYPE_CHECKING, Any, Optional

import anyio
import httpx
import sniffio

from prefect.client.schemas.objects import State, StateType
from prefect.exceptions import MissingContextError, TerminationSignal
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.states import (
    Completed,
    Crashed,
    Failed,
    StateGroup,
    format_exception,
    is_state_iterable,
)
from prefect.utilities.collections import ensure_iterable

if TYPE_CHECKING:
    import logging

    from prefect.results import (
        R,
        ResultStore,
    )

logger: "logging.Logger" = get_logger("states")


def exception_to_crashed_state_sync(
    exc: BaseException,
    result_store: Optional["ResultStore"] = None,
) -> State:
    """
    Sync version of exception_to_crashed_state.

    Takes an exception that occurs _outside_ of user code and converts it to a
    'Crash' exception with a 'Crashed' state.
    """
    state_message = None

    # Check for anyio cancellation - but only if we're in an async context.
    # anyio.get_cancelled_exc_class() requires an active async backend;
    # calling it from sync-only code raises an error. Since anyio cancellation
    # exceptions can only occur in async contexts anyway, we can safely skip
    # this check when no async backend is running.
    # anyio 4.12+ raises anyio.NoEventLoopError, older versions raise
    # sniffio.AsyncLibraryNotFoundError. Catch both for compatibility.
    # TODO: remove sniffio handling once anyio lower bound is >=4.12.1
    try:
        cancelled_exc_class = anyio.get_cancelled_exc_class()
        is_anyio_cancelled = isinstance(exc, cancelled_exc_class)
    except (sniffio.AsyncLibraryNotFoundError, anyio.NoEventLoopError):
        is_anyio_cancelled = False

    if is_anyio_cancelled:
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
        key = uuid.uuid4().hex
        data = result_store.create_result_record(exc, key=key)
    else:
        # Attach the exception for local usage, will not be available when retrieved
        # from the API
        data = exc

    return Crashed(message=state_message, data=data)


def exception_to_failed_state_sync(
    exc: Optional[BaseException] = None,
    result_store: Optional["ResultStore"] = None,
    write_result: bool = False,
    **kwargs: Any,
) -> State[BaseException]:
    """
    Sync version of exception_to_failed_state.

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
        key = uuid.uuid4().hex
        data = result_store.create_result_record(exc, key=key)
        if write_result:
            try:
                result_store.persist_result_record(data)
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


def return_value_to_state_sync(
    retval: "R",
    result_store: "ResultStore",
    key: Optional[str] = None,
    expiration: Optional[datetime.datetime] = None,
    write_result: bool = False,
) -> "State[R]":
    """
    Sync version of return_value_to_state.

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
    from prefect.results import (
        ResultRecord,
        ResultRecordMetadata,
    )

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
        if not isinstance(state.data, (ResultRecord, ResultRecordMetadata)):
            result_record = result_store.create_result_record(
                state.data,
                key=key,
                expiration=expiration,
            )
            if write_result:
                try:
                    result_store.persist_result_record(result_record)
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
                result_store.persist_result_record(result_record)
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
    if isinstance(data, ResultRecord):
        return Completed(data=data)
    else:
        result_record = result_store.create_result_record(
            data,
            key=key,
            expiration=expiration,
        )
        if write_result:
            try:
                result_store.persist_result_record(result_record)
            except Exception as exc:
                local_logger.warning(
                    "Encountered an error while persisting result: %s Execution will continue, but the result has not been persisted",
                    exc,
                )
        return Completed(data=result_record)
