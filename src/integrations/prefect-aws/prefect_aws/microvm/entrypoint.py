"""Process entrypoint for a Prefect flow run in an AWS Lambda MicroVM."""

from __future__ import annotations

import os
import signal
import socket
import threading
from pathlib import Path
from urllib.parse import urlsplit

from prefect.context import refresh_global_settings_context
from prefect.logging import get_logger
from prefect_aws.microvm.payload import InvalidRunHookPayload, RunHookRequest
from prefect_aws.microvm.server import HOOK_SERVER_PORT, LifecycleHookServer
from prefect_aws.microvm.supervisor import report_crash, supervise_flow_run

logger = get_logger("prefect_aws.microvm")

DEFAULT_PORTS = {"http": 80, "https": 443}
HOSTS_FILE_PATH = Path("/etc/hosts")
NSSWITCH_CONF_PATH = Path("/etc/nsswitch.conf")


def warm_name_lookup() -> None:
    """
    Look up `127.0.0.1`, and `localhost` when `/etc/hosts` answers it. A lookup
    error is logged and ignored.
    """
    # In a restored MicroVM, the first API host lookup took 0.485 s with no
    # lookup before the snapshot, 0.318 s after a `127.0.0.1` lookup, and
    # 0.174 s after a `127.0.0.1` and a `localhost` lookup. `localhost` is looked
    # up only when the hosts file answers it, because a lookup that waits on DNS
    # would delay the answer to `/ready`.
    _look_up_and_ignore_errors("127.0.0.1")
    if localhost_is_answered_from_hosts_file():
        _look_up_and_ignore_errors("localhost")


def localhost_is_answered_from_hosts_file() -> bool:
    """
    Return whether a `localhost` lookup is answered from `/etc/hosts` before any
    other name service is asked.

    Returns:
        True if `/etc/hosts` has a `localhost` entry and `files` is the first
        source on the `hosts:` line of `/etc/nsswitch.conf`. False otherwise,
        including when either file cannot be read.
    """
    try:
        hosts_file = HOSTS_FILE_PATH.read_text(encoding="utf-8")
        nsswitch_conf = NSSWITCH_CONF_PATH.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    return _hosts_file_has_localhost(hosts_file) and _hosts_sources_start_with_files(
        nsswitch_conf
    )


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

    SIGTERM is blocked from the `/run` request until the flow run's process
    exists, then forwarded to it.

    Args:
        port: The port to serve the lifecycle hooks on.

    Returns:
        0 if the flow run's process exited 0. 1 if the `/run` request was
        rejected, the run's settings could not be loaded, or the flow run's
        process failed.
    """
    warm_name_lookup()
    server = LifecycleHookServer(("0.0.0.0", port))
    threading.Thread(
        target=server.serve_forever, name="microvm-lifecycle-hooks", daemon=True
    ).start()

    run_request = server.wait_for_run_request()
    # As PID 1 this process drops a SIGTERM it has no handler for. Blocked, the
    # SIGTERM stays pending until `supervise_flow_run` can forward it.
    signal_mask_before_run = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
    try:
        return _run(server, run_request, signal_mask_before_run)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, signal_mask_before_run)


def _run(
    server: LifecycleHookServer,
    run_request: RunHookRequest | InvalidRunHookPayload,
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


def _look_up_and_ignore_errors(host: str) -> None:
    try:
        socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        logger.debug("Could not resolve %s.", host, exc_info=True)


def _hosts_file_has_localhost(hosts_file: str) -> bool:
    for line in hosts_file.splitlines():
        fields = line.partition("#")[0].split()
        if "localhost" in fields[1:]:
            return True
    return False


def _hosts_sources_start_with_files(nsswitch_conf: str) -> bool:
    for line in nsswitch_conf.splitlines():
        database, separator, sources = line.partition("#")[0].partition(":")
        if separator and database.strip() == "hosts":
            return sources.split()[:1] == ["files"]
    return False


def _resolve_api_host(hostname: str, port: int) -> None:
    try:
        socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (OSError, UnicodeError):
        logger.debug(
            "Could not resolve the Prefect API host %s.", hostname, exc_info=True
        )
