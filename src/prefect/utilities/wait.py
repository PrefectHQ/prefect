import asyncio
import time
from logging import Logger
from typing import Awaitable, Callable

from prefect.exceptions import JobRunTimeoutError


async def async_wait_until_state(
    in_final_state_fn: Awaitable[Callable],
    get_state_fn: Awaitable[Callable],
    log_state_fn: Callable = None,
    interval_seconds: int = 1,
    timeout_seconds: int = 60,
    logger: Logger = None,
    **get_state_kwargs,
):
    """
    Wait until the job run reaches a specific state.

    Args:
        in_final_state_fn: An async function that accepts a run state
        and returns a boolean indicating whether the job run is in a final state.
        get_state_fn: An async function that returns the current state of the job run.
        log_state_fn: A callable that accepts a run state and makes it human readable.
        interval_seconds: The number of seconds to wait between checks of
            the job run's state.
        timeout_seconds: The maximum amount of time, in seconds, to wait
            for the job run to reach the final state.
    """
    start_time = time.time()
    last_state = run_state = None
    while not in_final_state_fn(run_state):
        run_state = await get_state_fn(**get_state_kwargs)
        if run_state != last_state:
            if logger is not None:
                logger.info("Job has new state: %s", log_state_fn(run_state))
            last_state = run_state

        elapsed_time_seconds = time.time() - start_time
        if elapsed_time_seconds > timeout_seconds:
            raise JobRunTimeoutError(
                f"Max wait time of {timeout_seconds} seconds exceeded while waiting"
            )
        await asyncio.sleep(interval_seconds)
