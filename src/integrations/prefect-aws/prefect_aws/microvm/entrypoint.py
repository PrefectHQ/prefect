"""Process entrypoint for a Prefect flow run in an AWS Lambda MicroVM."""

from __future__ import annotations

import os
import socket
import threading
from urllib.parse import urlsplit

from prefect.context import refresh_global_settings_context
from prefect.logging import get_logger
from prefect_aws.microvm.payload import InvalidRunHookPayload
from prefect_aws.microvm.server import HOOK_SERVER_PORT, LifecycleHookServer
from prefect_aws.microvm.supervisor import report_crash, supervise_flow_run

logger = get_logger("prefect_aws.microvm")

DEFAULT_PORTS = {"http": 80, "https": 443}


def warm_name_lookup() -> None:
    """
    Resolve `localhost` once. A lookup error is logged and ignored.
    """
    # In a restored MicroVM the first name lookup in a process is slow. One made
    # before the snapshot shortens it.
    try:
        socket.getaddrinfo("localhost", None, type=socket.SOCK_STREAM)
    except OSError:
        logger.debug("Could not resolve localhost.", exc_info=True)


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

    Args:
        port: The port to serve the lifecycle hooks on.

    Returns:
        0 if the flow run's process exited 0. 1 if the `/run` request was
        rejected, the run's settings could not be loaded, or the flow run's
        process failed.
    """
    # On its own thread, so that a stalled lookup cannot delay the answer to
    # `/ready`.
    name_lookup_warm_up = threading.Thread(
        target=warm_name_lookup, name="microvm-name-lookup-warm-up", daemon=True
    )
    name_lookup_warm_up.start()
    server = LifecycleHookServer(("0.0.0.0", port))
    threading.Thread(
        target=server.serve_forever, name="microvm-lifecycle-hooks", daemon=True
    ).start()

    run_request = server.wait_for_run_request()
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
    # forks. The resolver's own timeout and attempts bound these waits.
    name_lookup_warm_up.join()
    if api_host_lookup is not None:
        api_host_lookup.join()

    # The flow run is forked from this thread, so it runs on the child's main
    # thread, where the engine can install its signal handlers.
    return supervise_flow_run(run_request.payload)


def _stop_hook_server(server: LifecycleHookServer) -> None:
    server.stop_serving()
    # Frees the hook port for flow code. A hook connection after this point is
    # refused instead of waiting on a server that no longer answers.
    server.server_close()


def _resolve_api_host(hostname: str, port: int) -> None:
    try:
        socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        logger.debug(
            "Could not resolve the Prefect API host %s.", hostname, exc_info=True
        )
