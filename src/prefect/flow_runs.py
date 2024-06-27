from typing import (
    TYPE_CHECKING,
    Dict,
    Optional,
    Type,
    TypeVar,
    overload,
)
from uuid import UUID, uuid4

import anyio

from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import FlowRun
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
    FlowRunWaitTimeout,
    NotPausedError,
    Pause,
)
from prefect.input import keyset_from_paused_state
from prefect.input.run_input import run_input_subclass_from_type
from prefect.logging import get_logger
from prefect.logging.loggers import (
    get_run_logger,
)
from prefect.states import (
    Paused,
    Suspended,
)
from prefect.utilities.asyncutils import (
    sync_compatible,
)
from prefect.utilities.engine import (
    propose_state,
)

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


@inject_client
async def wait_for_flow_run(
    flow_run_id: UUID,
    timeout: Optional[int] = 10800,
    poll_interval: int = 5,
    client: Optional["PrefectClient"] = None,
    log_states: bool = False,
) -> FlowRun:
    """
    Waits for the prefect flow run to finish and returns the FlowRun

    Args:
        flow_run_id: The flow run ID for the flow run to wait for.
        timeout: The wait timeout in seconds. Defaults to 10800 (3 hours).
        poll_interval: The poll interval in seconds. Defaults to 5.

    Returns:
        FlowRun: The finished flow run.

    Raises:
        prefect.exceptions.FlowWaitTimeout: If flow run goes over the timeout.

    Examples:
        Create a flow run for a deployment and wait for it to finish:
            ```python
            import asyncio

            from prefect.client.orchestration import get_client
            from prefect.flow_runs import wait_for_flow_run

            async def main():
                async with get_client() as client:
                    flow_run = await client.create_flow_run_from_deployment(deployment_id="my-deployment-id")
                    flow_run = await wait_for_flow_run(flow_run_id=flow_run.id)
                    print(flow_run.state)

            if __name__ == "__main__":
                asyncio.run(main())

            ```

        Trigger multiple flow runs and wait for them to finish:
            ```python
            import asyncio

            from prefect.client.orchestration import get_client
            from prefect.flow_runs import wait_for_flow_run

            async def main(num_runs: int):
                async with get_client() as client:
                    flow_runs = [
                        await client.create_flow_run_from_deployment(deployment_id="my-deployment-id")
                        for _
                        in range(num_runs)
                    ]
                    coros = [wait_for_flow_run(flow_run_id=flow_run.id) for flow_run in flow_runs]
                    finished_flow_runs = await asyncio.gather(*coros)
                    print([flow_run.state for flow_run in finished_flow_runs])

            if __name__ == "__main__":
                asyncio.run(main(num_runs=10))

            ```
    """
    assert client is not None, "Client injection failed"
    logger = get_logger()
    with anyio.move_on_after(timeout):
        while True:
            flow_run = await client.read_flow_run(flow_run_id)
            flow_state = flow_run.state
            if log_states:
                logger.info(f"Flow run is in state {flow_run.state.name!r}")
            if flow_state and flow_state.is_final():
                return flow_run
            await anyio.sleep(poll_interval)
    raise FlowRunWaitTimeout(
        f"Flow run with ID {flow_run_id} exceeded watch timeout of {timeout} seconds"
    )


R = TypeVar("R")
T = TypeVar("T")


@overload
async def pause_flow_run(
    wait_for_input: None = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    key: Optional[str] = None,
) -> None:
    ...


@overload
async def pause_flow_run(
    wait_for_input: Type[T],
    timeout: int = 3600,
    poll_interval: int = 10,
    key: Optional[str] = None,
) -> T:
    ...


@sync_compatible
async def pause_flow_run(
    wait_for_input: Optional[Type[T]] = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    key: Optional[str] = None,
) -> Optional[T]:
    """
    Pauses the current flow run by blocking execution until resumed.

    When called within a flow run, execution will block and no downstream tasks will
    run until the flow is resumed. Task runs that have already started will continue
    running. A timeout parameter can be passed that will fail the flow run if it has not
    been resumed within the specified time.

    Args:
        timeout: the number of seconds to wait for the flow to be resumed before
            failing. Defaults to 1 hour (3600 seconds). If the pause timeout exceeds
            any configured flow-level timeout, the flow might fail even after resuming.
        poll_interval: The number of seconds between checking whether the flow has been
            resumed. Defaults to 10 seconds.
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
    return await _in_process_pause(
        timeout=timeout,
        poll_interval=poll_interval,
        key=key,
        wait_for_input=wait_for_input,
    )


@inject_client
async def _in_process_pause(
    timeout: int = 3600,
    poll_interval: int = 10,
    key: Optional[str] = None,
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
        timeout_seconds=timeout, reschedule=False, pause_key=pause_key
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
    configured with the `persist_result` option.

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


def _observed_flow_pauses(context: FlowRunContext) -> int:
    if "counter" not in context.observed_flow_pauses:
        context.observed_flow_pauses["counter"] = 1
    else:
        context.observed_flow_pauses["counter"] += 1
    return context.observed_flow_pauses["counter"]
