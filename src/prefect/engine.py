import os
import sys
from typing import (
    Dict,
    Optional,
    Type,
    TypeVar,
    overload,
)
from uuid import UUID, uuid4

import anyio
from typing_extensions import Literal

from prefect._internal.compatibility.deprecated import deprecated_parameter
from prefect._internal.compatibility.experimental import experimental_parameter
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import (
    StateType,
)
from prefect.client.schemas.responses import SetStateStatus
from prefect.client.utilities import inject_client
from prefect.context import (
    FlowRunContext,
    TaskRunContext,
)
from prefect.exceptions import (
    Abort,
    FlowPauseTimeout,
    NotPausedError,
    Pause,
)
from prefect.input import keyset_from_paused_state
from prefect.input.run_input import run_input_subclass_from_type
from prefect.logging.loggers import (
    get_logger,
    get_run_logger,
)
from prefect.states import (
    Paused,
    Suspended,
)
from prefect.utilities.asyncutils import (
    run_coro_as_sync,
    sync_compatible,
)
from prefect.utilities.engine import (
    _observed_flow_pauses,
    propose_state,
)

R = TypeVar("R")
T = TypeVar("T")
EngineReturnType = Literal["future", "state", "result"]

NUM_CHARS_DYNAMIC_KEY = 8

engine_logger = get_logger("engine")


@overload
async def pause_flow_run(
    wait_for_input: None = None,
    flow_run_id: UUID = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
) -> None:
    ...


@overload
async def pause_flow_run(
    wait_for_input: Type[T],
    flow_run_id: UUID = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
) -> T:
    ...


@sync_compatible
@deprecated_parameter(
    "flow_run_id", start_date="Dec 2023", help="Use `suspend_flow_run` instead."
)
@deprecated_parameter(
    "reschedule",
    start_date="Dec 2023",
    when=lambda p: p is True,
    help="Use `suspend_flow_run` instead.",
)
@experimental_parameter(
    "wait_for_input", group="flow_run_input", when=lambda y: y is not None
)
async def pause_flow_run(
    wait_for_input: Optional[Type[T]] = None,
    flow_run_id: UUID = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
) -> Optional[T]:
    """
    Pauses the current flow run by blocking execution until resumed.

    When called within a flow run, execution will block and no downstream tasks will
    run until the flow is resumed. Task runs that have already started will continue
    running. A timeout parameter can be passed that will fail the flow run if it has not
    been resumed within the specified time.

    Args:
        flow_run_id: a flow run id. If supplied, this function will attempt to pause
            the specified flow run outside of the flow run process. When paused, the
            flow run will continue execution until the NEXT task is orchestrated, at
            which point the flow will exit. Any tasks that have already started will
            run until completion. When resumed, the flow run will be rescheduled to
            finish execution. In order pause a flow run in this way, the flow needs to
            have an associated deployment and results need to be configured with the
            `persist_results` option.
        timeout: the number of seconds to wait for the flow to be resumed before
            failing. Defaults to 1 hour (3600 seconds). If the pause timeout exceeds
            any configured flow-level timeout, the flow might fail even after resuming.
        poll_interval: The number of seconds between checking whether the flow has been
            resumed. Defaults to 10 seconds.
        reschedule: Flag that will reschedule the flow run if resumed. Instead of
            blocking execution, the flow will gracefully exit (with no result returned)
            instead. To use this flag, a flow needs to have an associated deployment and
            results need to be configured with the `persist_results` option.
        key: An optional key to prevent calling pauses more than once. This defaults to
            the number of pauses observed by the flow so far, and prevents pauses that
            use the "reschedule" option from running the same pause twice. A custom key
            can be supplied for custom pausing behavior.
        wait_for_input: a subclass of `RunInput` or any type supported by
            Pydantic. If provided when the flow pauses, the flow will wait for the
            input to be provided before resuming. If the flow is resumed without
            providing the input, the flow will fail. If the flow is resumed with the
            input, the flow will resume and the input will be loaded and returned
            from this function.

    Example:
    ```python
    @task
    def task_one():
        for i in range(3):
            sleep(1)

    @flow
    def my_flow():
        terminal_state = task_one.submit(return_state=True)
        if terminal_state.type == StateType.COMPLETED:
            print("Task one succeeded! Pausing flow run..")
            pause_flow_run(timeout=2)
        else:
            print("Task one failed. Skipping pause flow run..")
    ```

    """
    if flow_run_id:
        if wait_for_input is not None:
            raise RuntimeError("Cannot wait for input when pausing out of process.")

        return await _out_of_process_pause(
            flow_run_id=flow_run_id,
            timeout=timeout,
            reschedule=reschedule,
            key=key,
        )
    else:
        return await _in_process_pause(
            timeout=timeout,
            poll_interval=poll_interval,
            reschedule=reschedule,
            key=key,
            wait_for_input=wait_for_input,
        )


@inject_client
async def _in_process_pause(
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule=False,
    key: str = None,
    client=None,
    wait_for_input: Optional[T] = None,
) -> Optional[T]:
    if TaskRunContext.get():
        raise RuntimeError("Cannot pause task runs.")

    context = FlowRunContext.get()
    if not context:
        raise RuntimeError("Flow runs can only be paused from within a flow run.")

    logger = get_run_logger(context=context)

    pause_counter = _observed_flow_pauses(context)
    pause_key = key or str(pause_counter)

    logger.info("Pausing flow, execution will continue when this flow run is resumed.")

    proposed_state = Paused(
        timeout_seconds=timeout, reschedule=reschedule, pause_key=pause_key
    )

    if wait_for_input:
        wait_for_input = run_input_subclass_from_type(wait_for_input)
        run_input_keyset = keyset_from_paused_state(proposed_state)
        proposed_state.state_details.run_input_keyset = run_input_keyset

    try:
        state = await propose_state(
            client=client,
            state=proposed_state,
            flow_run_id=context.flow_run.id,
        )
    except Abort as exc:
        # Aborted pause requests mean the pause is not allowed
        raise RuntimeError(f"Flow run cannot be paused: {exc}")

    if state.is_running():
        # The orchestrator rejected the paused state which means that this
        # pause has happened before (via reschedule) and the flow run has
        # been resumed.
        if wait_for_input:
            # The flow run wanted input, so we need to load it and return it
            # to the user.
            await wait_for_input.load(run_input_keyset)

        return

    if not state.is_paused():
        # If we receive anything but a PAUSED state, we are unable to continue
        raise RuntimeError(
            f"Flow run cannot be paused. Received non-paused state from API: {state}"
        )

    if wait_for_input:
        # We're now in a paused state and the flow run is waiting for input.
        # Save the schema of the users `RunInput` subclass, stored in
        # `wait_for_input`, so the UI can display the form and we can validate
        # the input when the flow is resumed.
        await wait_for_input.save(run_input_keyset)

    if reschedule:
        # If a rescheduled pause, exit this process so the run can be resubmitted later
        raise Pause(state=state)

    # Otherwise, block and check for completion on an interval
    with anyio.move_on_after(timeout):
        # attempt to check if a flow has resumed at least once
        initial_sleep = min(timeout / 2, poll_interval)
        await anyio.sleep(initial_sleep)
        while True:
            flow_run = await client.read_flow_run(context.flow_run.id)
            if flow_run.state.is_running():
                logger.info("Resuming flow run execution!")
                if wait_for_input:
                    return await wait_for_input.load(run_input_keyset)
                return
            await anyio.sleep(poll_interval)

    # check one last time before failing the flow
    flow_run = await client.read_flow_run(context.flow_run.id)
    if flow_run.state.is_running():
        logger.info("Resuming flow run execution!")
        if wait_for_input:
            return await wait_for_input.load(run_input_keyset)
        return

    raise FlowPauseTimeout("Flow run was paused and never resumed.")


@inject_client
async def _out_of_process_pause(
    flow_run_id: UUID,
    timeout: int = 3600,
    reschedule: bool = True,
    key: str = None,
    client=None,
):
    if reschedule:
        raise RuntimeError(
            "Pausing a flow run out of process requires the `reschedule` option set to"
            " True."
        )

    response = await client.set_flow_run_state(
        flow_run_id,
        Paused(timeout_seconds=timeout, reschedule=True, pause_key=key),
    )
    if response.status != SetStateStatus.ACCEPT:
        raise RuntimeError(response.details.reason)


@overload
async def suspend_flow_run(
    wait_for_input: None = None,
    flow_run_id: Optional[UUID] = None,
    timeout: Optional[int] = 3600,
    key: Optional[str] = None,
    client: PrefectClient = None,
) -> None:
    ...


@overload
async def suspend_flow_run(
    wait_for_input: Type[T],
    flow_run_id: Optional[UUID] = None,
    timeout: Optional[int] = 3600,
    key: Optional[str] = None,
    client: PrefectClient = None,
) -> T:
    ...


@sync_compatible
@inject_client
@experimental_parameter(
    "wait_for_input", group="flow_run_input", when=lambda y: y is not None
)
async def suspend_flow_run(
    wait_for_input: Optional[Type[T]] = None,
    flow_run_id: Optional[UUID] = None,
    timeout: Optional[int] = 3600,
    key: Optional[str] = None,
    client: PrefectClient = None,
) -> Optional[T]:
    """
    Suspends a flow run by stopping code execution until resumed.

    When suspended, the flow run will continue execution until the NEXT task is
    orchestrated, at which point the flow will exit. Any tasks that have
    already started will run until completion. When resumed, the flow run will
    be rescheduled to finish execution. In order suspend a flow run in this
    way, the flow needs to have an associated deployment and results need to be
    configured with the `persist_results` option.

    Args:
        flow_run_id: a flow run id. If supplied, this function will attempt to
            suspend the specified flow run. If not supplied will attempt to
            suspend the current flow run.
        timeout: the number of seconds to wait for the flow to be resumed before
            failing. Defaults to 1 hour (3600 seconds). If the pause timeout
            exceeds any configured flow-level timeout, the flow might fail even
            after resuming.
        key: An optional key to prevent calling suspend more than once. This
            defaults to a random string and prevents suspends from running the
            same suspend twice. A custom key can be supplied for custom
            suspending behavior.
        wait_for_input: a subclass of `RunInput` or any type supported by
            Pydantic. If provided when the flow suspends, the flow will remain
            suspended until receiving the input before resuming. If the flow is
            resumed without providing the input, the flow will fail. If the flow is
            resumed with the input, the flow will resume and the input will be
            loaded and returned from this function.
    """
    context = FlowRunContext.get()

    if flow_run_id is None:
        if TaskRunContext.get():
            raise RuntimeError("Cannot suspend task runs.")

        if context is None or context.flow_run is None:
            raise RuntimeError(
                "Flow runs can only be suspended from within a flow run."
            )

        logger = get_run_logger(context=context)
        logger.info(
            "Suspending flow run, execution will be rescheduled when this flow run is"
            " resumed."
        )
        flow_run_id = context.flow_run.id
        suspending_current_flow_run = True
        pause_counter = _observed_flow_pauses(context)
        pause_key = key or str(pause_counter)
    else:
        # Since we're suspending another flow run we need to generate a pause
        # key that won't conflict with whatever suspends/pauses that flow may
        # have. Since this method won't be called during that flow run it's
        # okay that this is non-deterministic.
        suspending_current_flow_run = False
        pause_key = key or str(uuid4())

    proposed_state = Suspended(timeout_seconds=timeout, pause_key=pause_key)

    if wait_for_input:
        wait_for_input = run_input_subclass_from_type(wait_for_input)
        run_input_keyset = keyset_from_paused_state(proposed_state)
        proposed_state.state_details.run_input_keyset = run_input_keyset

    try:
        state = await propose_state(
            client=client,
            state=proposed_state,
            flow_run_id=flow_run_id,
        )
    except Abort as exc:
        # Aborted requests mean the suspension is not allowed
        raise RuntimeError(f"Flow run cannot be suspended: {exc}")

    if state.is_running():
        # The orchestrator rejected the suspended state which means that this
        # suspend has happened before and the flow run has been resumed.
        if wait_for_input:
            # The flow run wanted input, so we need to load it and return it
            # to the user.
            return await wait_for_input.load(run_input_keyset)
        return

    if not state.is_paused():
        # If we receive anything but a PAUSED state, we are unable to continue
        raise RuntimeError(
            f"Flow run cannot be suspended. Received unexpected state from API: {state}"
        )

    if wait_for_input:
        await wait_for_input.save(run_input_keyset)

    if suspending_current_flow_run:
        # Exit this process so the run can be resubmitted later
        raise Pause()


@sync_compatible
async def resume_flow_run(flow_run_id, run_input: Optional[Dict] = None):
    """
    Resumes a paused flow.

    Args:
        flow_run_id: the flow_run_id to resume
        run_input: a dictionary of inputs to provide to the flow run.
    """
    client = get_client()
    async with client:
        flow_run = await client.read_flow_run(flow_run_id)

        if not flow_run.state.is_paused():
            raise NotPausedError("Cannot resume a run that isn't paused!")

        response = await client.resume_flow_run(flow_run_id, run_input=run_input)

    if response.status == SetStateStatus.REJECT:
        if response.state.type == StateType.FAILED:
            raise FlowPauseTimeout("Flow run can no longer be resumed.")
        else:
            raise RuntimeError(f"Cannot resume this run: {response.details.reason}")


if __name__ == "__main__":
    try:
        flow_run_id = UUID(
            sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PREFECT__FLOW_RUN_ID")
        )
    except Exception:
        engine_logger.error(
            f"Invalid flow run id. Received arguments: {sys.argv}", exc_info=True
        )
        exit(1)

    try:
        from prefect.flow_engine import (
            load_flow_and_flow_run,
            run_flow_async,
            run_flow_sync,
        )

        flow_run, flow = load_flow_and_flow_run(flow_run_id=flow_run_id)
        # run the flow
        if flow.isasync:
            run_coro_as_sync(run_flow_async(flow, flow_run=flow_run))
        else:
            run_flow_sync(flow, flow_run=flow_run)
    except Abort as exc:
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' aborted by orchestrator:"
            f" {exc}"
        )
        exit(0)
    except Pause as exc:
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' is paused: {exc}"
        )
        exit(0)
    except Exception:
        engine_logger.error(
            (
                f"Engine execution of flow run '{flow_run_id}' exited with unexpected "
                "exception"
            ),
            exc_info=True,
        )
        exit(1)
    except BaseException:
        engine_logger.error(
            (
                f"Engine execution of flow run '{flow_run_id}' interrupted by base "
                "exception"
            ),
            exc_info=True,
        )
        # Let the exit code be determined by the base exception type
        raise
