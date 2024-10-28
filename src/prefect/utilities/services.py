import sys
import threading
from collections import deque
from traceback import format_exception
from types import TracebackType
from typing import Callable, Coroutine, Deque, Optional, Tuple
from wsgiref.simple_server import WSGIServer

import anyio
import httpx

from prefect.logging.loggers import get_logger
from prefect.settings import PREFECT_CLIENT_METRICS_ENABLED, PREFECT_CLIENT_METRICS_PORT
from prefect.utilities.collections import distinct
from prefect.utilities.math import clamped_poisson_interval

logger = get_logger("utilities.services.critical_service_loop")


async def critical_service_loop(
    workload: Callable[..., Coroutine],
    interval: float,
    memory: int = 10,
    consecutive: int = 3,
    backoff: int = 1,
    printer: Callable[..., None] = print,
    run_once: bool = False,
    jitter_range: Optional[float] = None,
):
    """
    Runs the given `workload` function on the specified `interval`, while being
    forgiving of intermittent issues like temporary HTTP errors.  If more than a certain
    number of `consecutive` errors occur, print a summary of up to `memory` recent
    exceptions to `printer`, then begin backoff.

    The loop will exit after reaching the consecutive error limit `backoff` times.
    On each backoff, the interval will be doubled. On a successful loop, the backoff
    will be reset.

    Args:
        workload: the function to call
        interval: how frequently to call it
        memory: how many recent errors to remember
        consecutive: how many consecutive errors must we see before we begin backoff
        backoff: how many times we should allow consecutive errors before exiting
        printer: a `print`-like function where errors will be reported
        run_once: if set, the loop will only run once then return
        jitter_range: if set, the interval will be a random variable (rv) drawn from
            a clamped Poisson distribution where lambda = interval and the rv is bound
            between `interval * (1 - range) < rv < interval * (1 + range)`
    """

    track_record: Deque[bool] = deque([True] * consecutive, maxlen=consecutive)
    failures: Deque[Tuple[Exception, TracebackType]] = deque(maxlen=memory)
    backoff_count = 0

    while True:
        try:
            workload_display_name = (
                workload.__name__ if hasattr(workload, "__name__") else workload
            )
            logger.debug(f"Starting run of {workload_display_name!r}")
            await workload()

            # Reset the backoff count on success; we may want to consider resetting
            # this only if the track record is _all_ successful to avoid ending backoff
            # prematurely
            if backoff_count > 0:
                printer("Resetting backoff due to successful run.")
                backoff_count = 0

            track_record.append(True)
        except httpx.TransportError as exc:
            # httpx.TransportError is the base class for any kind of communications
            # error, like timeouts, connection failures, etc.  This does _not_ cover
            # routine HTTP error codes (even 5xx errors like 502/503) so this
            # handler should not be attempting to cover cases where the Prefect server
            # or Prefect Cloud is having an outage (which will be covered by the
            # exception clause below)
            track_record.append(False)
            failures.append((exc, sys.exc_info()[-1]))
            logger.debug(
                f"Run of {workload!r} failed with TransportError", exc_info=exc
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code >= 500:
                # 5XX codes indicate a potential outage of the Prefect API which is
                # likely to be temporary and transient.  Don't quit over these unless
                # it is prolonged.
                track_record.append(False)
                failures.append((exc, sys.exc_info()[-1]))
                logger.debug(
                    f"Run of {workload!r} failed with HTTPStatusError", exc_info=exc
                )
            else:
                raise

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
        # would be a very low-probability occurrence, but in the everything-is-on-fire
        # distribution, that is a high-probability occurrence.
        #
        # Remarkably, we only need to look back for a small number of consecutive
        # errors to have reasonable confidence that this is indeed an anomaly.
        # @anticorrelator and @chrisguidry estimated that we should only need to look
        # back for 3 consecutive errors.
        if not any(track_record):
            # We've failed enough times to be sure something is wrong, the writing is
            # on the wall.  Let's explain what we've seen and exit.
            printer(
                f"\nFailed the last {consecutive} attempts. "
                "Please check your environment and configuration."
            )

            printer("Examples of recent errors:\n")

            failures_by_type = distinct(
                reversed(failures),
                key=lambda pair: type(pair[0]),  # Group by the type of exception
            )
            for exception, traceback in failures_by_type:
                printer("".join(format_exception(None, exception, traceback)))
                printer()

            backoff_count += 1

            if backoff_count >= backoff:
                raise RuntimeError("Service exceeded error threshold.")

            # Reset the track record
            track_record.extend([True] * consecutive)
            failures.clear()
            printer(
                "Backing off due to consecutive errors, using increased interval of "
                f" {interval * 2**backoff_count}s."
            )

        if run_once:
            return

        if jitter_range is not None:
            sleep = clamped_poisson_interval(interval, clamping_factor=jitter_range)
        else:
            sleep = interval * 2**backoff_count

        await anyio.sleep(sleep)


_metrics_server: Optional[Tuple[WSGIServer, threading.Thread]] = None


def start_client_metrics_server():
    """Start the process-wide Prometheus metrics server for client metrics (if enabled
    with `PREFECT_CLIENT_METRICS_ENABLED`) on the port `PREFECT_CLIENT_METRICS_PORT`."""
    if not PREFECT_CLIENT_METRICS_ENABLED:
        return

    global _metrics_server
    if _metrics_server:
        return

    from prometheus_client import start_http_server

    _metrics_server = start_http_server(port=PREFECT_CLIENT_METRICS_PORT.value())


def stop_client_metrics_server():
    """Start the process-wide Prometheus metrics server for client metrics, if it has
    previously been started"""
    global _metrics_server
    if _metrics_server:
        server, thread = _metrics_server
        server.shutdown()
        thread.join()
        _metrics_server = None
