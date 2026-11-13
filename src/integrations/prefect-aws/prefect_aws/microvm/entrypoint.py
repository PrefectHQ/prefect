"""Process entrypoint for a Prefect flow run in an AWS Lambda MicroVM."""

from __future__ import annotations

import os
import signal
import socket
import threading
from urllib.parse import urlsplit

from prefect.context import refresh_global_settings_context
from prefect.logging import get_logger
from prefect_aws.microvm.payload import InvalidRunHookPayload, RunHookRequest
from prefect_aws.microvm.server import HOOK_SERVER_PORT, LifecycleHookServer
from prefect_aws.microvm.supervisor import report_crash, supervise_flow_run

logger = get_logger("prefect_aws.microvm")

DEFAULT_PORTS = {"http": 80, "https": 443}


def start_name_lookup_warm_up() -> threading.Thread:
    """
    Start looking up `127.0.0.1` and then `localhost` on a daemon thread. A
    lookup error is logged and ignored.

    Returns:
        The thread doing the lookups.
    """
    warm_up = threading.Thread(
        target=_warm_name_lookup, name="microvm-name-lookup-warm-up", daemon=True
    )
    warm_up.start()
    return warm_up


def start_api_host_lookup(api_url: str | None) -> threading.Thread | None:
    """
    Start resolving the host of `api_url` on a daemon thread.

    Args:
        api_url: The Prefect API URL.

    Returns:
        The thread doing the lookup, or None if `api_url` is missing or is not
        an http or https URL with a hostname and a valid port.
    """
    if not api_url:
        return None
    try:
        parsed_url = urlsplit(api_url)
        if parsed_url.scheme not in DEFAULT_PORTS or not parsed_url.hostname:
            return None
        hostname = parsed_url.hostname
        port = parsed_url.port or DEFAULT_PORTS[parsed_url.scheme]
    except ValueError:
        return None
    lookup = threading.Thread(
        target=_resolve_api_host,
        args=(hostname, port),
        name="microvm-api-host-lookup",
        daemon=True,
    )
    lookup.start()
    return lookup


def main(port: int = HOOK_SERVER_PORT) -> int:
    """
    Serve the lifecycle hooks, run the flow run from the first `/run` request,
    and return the process exit code.

    SIGTERM is blocked before a valid `/run` request is answered, stays blocked
    until the flow run's process exists, and is then forwarded to it.

    Args:
        port: The port to serve the lifecycle hooks on.

    Returns:
        0 if the flow run's process exited 0. 1 if the `/run` request was
        rejected, the run's settings could not be loaded, or the flow run's
        process failed.
    """
    # As PID 1, a thread that takes a SIGTERM with no handler drops it. The
    # warm-up and server threads start with SIGTERM blocked, so a SIGTERM after
    # `/run` waits for the forwarding handler. The main thread unblocks it again
    # until `/run`, because a SIGTERM pending in the snapshot, taken after
    # `/ready`, would be pending in every restore.
    signal_mask_before_threads = signal.pthread_sigmask(
        signal.SIG_BLOCK, {signal.SIGTERM}
    )
    try:
        # A lookup before the snapshot shortens a restored MicroVM's first API
        # host lookup. `/ready` waits for it at most
        # `NAME_LOOKUP_WARM_UP_WAIT_SECONDS`, so a stalled resolver cannot hold
        # up the image build.
        name_lookup_warm_up = start_name_lookup_warm_up()
        server = LifecycleHookServer(
            ("0.0.0.0", port), name_lookup_warm_up=name_lookup_warm_up
        )
        threading.Thread(
            target=server.serve_forever, name="microvm-lifecycle-hooks", daemon=True
        ).start()
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, signal_mask_before_threads)

    run_request = server.wait_for_run_request()
    # Blocked, a SIGTERM stays pending until `supervise_flow_run` can forward
    # it. The `/run` handler waits for `allow_run_reply` before it sends its 200.
    signal_mask_before_run = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    try:
        server.allow_run_reply()
        return _run(server, run_request, name_lookup_warm_up, signal_mask_before_run)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, signal_mask_before_run)


def _run(
    server: LifecycleHookServer,
    run_request: RunHookRequest | InvalidRunHookPayload,
    name_lookup_warm_up: threading.Thread,
    signal_mask_before_run: set[signal.Signals],
) -> int:
    if isinstance(run_request, InvalidRunHookPayload):
        _stop_hook_server(server)
        return 1

    flow_run_id = run_request.payload.flow_run_id
    # In a restored MicroVM the first name lookup in a process is slow. A process
    # forked after a lookup inherits the warmed state.
    api_host_lookup = start_api_host_lookup(os.environ.get("PREFECT_API_URL"))
    hook_server_stopper = threading.Thread(
        target=_stop_hook_server,
        args=(server,),
        name="microvm-lifecycle-hooks-stopper",
        daemon=True,
    )
    hook_server_stopper.start()

    try:
        # Settings were resolved at import time, before `/run` set the
        # environment. The forked child inherits the refreshed settings.
        refresh_global_settings_context()
    except Exception:
        logger.exception("Could not load the settings for flow run %s.", flow_run_id)
        try:
            report_crash(flow_run_id, "could not load its settings")
        except Exception:
            logger.exception("Could not report flow run %s as crashed.", flow_run_id)
        hook_server_stopper.join()
        return 1

    # Waits for the hook handlers in progress, up to `stop_serving`'s timeout,
    # so that they finish before the fork.
    hook_server_stopper.join()
    # No thread may be inside the C library's name lookup when the process
    # forks. The resolver's own timeout and attempts bound this wait.
    if name_lookup_warm_up.is_alive():
        logger.warning(
            "The name lookup started before the image snapshot has not finished. "
            "Flow run %s will wait for it before it starts.",
            flow_run_id,
        )
    name_lookup_warm_up.join()
    if api_host_lookup is not None:
        api_host_lookup.join()

    # The flow run is forked from this thread, so it runs on the child's main
    # thread, where the engine can install its signal handlers.
    return supervise_flow_run(
        run_request.payload, restored_signal_mask=signal_mask_before_run
    )


def _stop_hook_server(server: LifecycleHookServer) -> None:
    server.stop_serving()
    # Frees the hook port for flow code. A hook connection after this point is
    # refused instead of waiting on a server that no longer answers.
    server.server_close()


def _warm_name_lookup() -> None:
    _look_up_and_ignore_errors("127.0.0.1")
    _look_up_and_ignore_errors("localhost")


def _look_up_and_ignore_errors(host: str) -> None:
    try:
        socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        logger.debug("Could not resolve %s.", host, exc_info=True)


def _resolve_api_host(hostname: str, port: int) -> None:
    try:
        socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        logger.debug(
            "Could not resolve the Prefect API host %s.", hostname, exc_info=True
        )
