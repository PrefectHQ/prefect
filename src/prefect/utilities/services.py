import traceback
from collections import deque
from typing import Callable, Coroutine, Deque, Optional

import anyio
import httpx

from prefect.utilities.collections import distinct


async def critical_service_loop(
    workload: Callable[..., Coroutine],
    interval: float,
    memory: int = 10,
    consecutive: int = 3,
    printer: Callable[..., None] = print,
):
    """
    Runs the the given `workload` function on the specified `interval`, while being
    forgiving of intermittent issues like temporary HTTP errors.  If more than a certain
    number of `consecutive` errors occur, print a summary of up to `memory` recent
    exceptions to `printer`, then exit.

    Args:
        `workload`: the function to call
        `interval`: how frequently to call it
        `memory`: how many recent errors to remember
        `consecutive`: how many consecutive errors must we see before we exit
        `printer`: a `print`-like function where errors will be reported
    """

    track_record: Deque[Optional[Exception]] = deque(maxlen=memory)

    while True:
        try:
            await workload()

            track_record.append(None)
        except httpx.TransportError as exc:
            # httpx.TransportError is the base class for any kind of communications
            # error, like timeouts, connection failures, etc.  This does _not_ cover
            # routine HTTP error codes (even 5xx errors like 502/503) so this
            # handler should not be attempting to cover cases where the Orion server
            # or Prefect Cloud is having an outage (which will be covered by the
            # exception clause below)
            track_record.append(exc)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (502, 503):
                # 502/503 indicate a potential outage of the Orion server or Prefect
                # Cloud, which is likely to be temporary and transient.  Don't quit
                # over these unless it is prolonged.
                track_record.append(exc)
            else:
                raise
        except KeyboardInterrupt:
            return

        # Decide whether to exit now based on recent history.
        #
        # Given some typical background error rate of, say, 1%, we may still observe
        # quite a few errors in our recent samples, but this is not necessarily a cause
        # for concern.
        #
        # Imagine two distributions that could reflect our situation at any time: the
        # everything-is-fine distribution of errors, and the everything-is-on-fire
        # distribution of errors. We are trying to determine which of those two worlds
        # we are currently experiencing.  We compare the likelihood that we'd draw N
        # consecutive errors from each.  In the everything-is-fine distribution, that
        # would be a very low-probability occurrance, but in the everything-is-on-fire
        # distribution, that is a high-probability occurrance.
        #
        # Remarkably, we only need to look back for a small number of consecutive
        # errors to have reasonable confidence that this is indeed an anomaly.
        # @anticorrelator and @chrisguidry estimated that we should only need to look
        # back for 3 consectutive errors.
        most_recent = list(reversed(track_record))
        if len(most_recent) > consecutive and all(most_recent[:consecutive]):
            # We've failed enough times to be sure something is wrong, the writing is
            # on the wall.  Let's explain what we've seen and exit.
            printer(
                f"\nFailed the last {consecutive} attempts.  "
                "Please check your environment and configuration."
            )

            printer("Examples of recent errors:\n")

            for exception in distinct(most_recent, key=lambda e: type(e)):
                if not exception:
                    continue
                printer("\n".join(traceback.format_exception_only(exception)))
                printer()
            return

        await anyio.sleep(interval)
