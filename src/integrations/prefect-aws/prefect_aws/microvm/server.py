"""HTTP server for the AWS Lambda MicroVM lifecycle hooks."""

from __future__ import annotations

import importlib
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from prefect.logging import get_logger
from prefect_aws.microvm.payload import (
    InvalidRunHookPayload,
    RunHookRequest,
    parse_run_hook_request,
)

logger = get_logger("prefect_aws.microvm")

HOOK_SERVER_PORT = 8080
HOOK_PATH_PREFIX = "/aws/lambda-microvms/runtime/v1/"
MAX_REQUEST_BODY_BYTES = 1024 * 1024

# Imported before `/ready` returns so that the MicroVM snapshot includes them
# and a restored MicroVM does not import them again for each flow run.
ENGINE_MODULES = (
    "prefect",
    "prefect.client.orchestration",
    "prefect.events.worker",
    "prefect.flow_engine",
    "prefect.logging.handlers",
)


def import_engine_modules() -> None:
    """Import the modules a flow run needs, so the snapshot includes them."""
    for module_name in ENGINE_MODULES:
        importlib.import_module(module_name)


class LifecycleHookServer(ThreadingHTTPServer):
    """
    Serves the MicroVM lifecycle hooks and hands the first valid `/run` request
    to the thread that calls `wait_for_run_request`.

    Hooks are accepted both at `/<hook>` and at
    `/aws/lambda-microvms/runtime/v1/<hook>`.
    """

    daemon_threads = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, LifecycleHookHandler)
        self._run_requests: queue.Queue[RunHookRequest | InvalidRunHookPayload] = (
            queue.Queue()
        )
        self._run_received = False
        self._run_lock = threading.Lock()

    def claim_run(self) -> bool:
        """Return True for the first `/run` request and False for every later one."""
        with self._run_lock:
            if self._run_received:
                return False
            self._run_received = True
            return True

    def submit_run(self, request: RunHookRequest | InvalidRunHookPayload) -> None:
        """Pass a parsed `/run` request, or the reason it was rejected, to `wait_for_run_request`."""
        self._run_requests.put(request)

    def wait_for_run_request(self) -> RunHookRequest | InvalidRunHookPayload:
        """Block until the first `/run` request has been answered, then return it."""
        return self._run_requests.get()


class LifecycleHookHandler(BaseHTTPRequestHandler):
    """Request handler for `LifecycleHookServer`."""

    server: LifecycleHookServer

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug(format, *args)

    def do_GET(self) -> None:
        if self._hook_name() == "ready":
            self._ready()
        else:
            self._reply(200)

    def do_POST(self) -> None:
        hook_name = self._hook_name()
        if hook_name == "ready":
            self._ready()
        elif hook_name == "run":
            self._run()
        else:
            logger.debug("Ignoring lifecycle hook %r.", hook_name)
            self._reply(200)

    def _hook_name(self) -> str:
        return self.path.split("?", 1)[0].removeprefix(HOOK_PATH_PREFIX).strip("/")

    def _ready(self) -> None:
        import_engine_modules()
        self._reply(200)

    def _run(self) -> None:
        if not self.server.claim_run():
            logger.warning("Ignoring a second `/run` request.")
            self._reply(409)
            return

        try:
            run_request = parse_run_hook_request(self._read_body())
        except InvalidRunHookPayload as exc:
            logger.error("Rejected `/run` request: %s", exc)
            self._reply(400)
            self.server.submit_run(exc)
            return

        logger.info(
            "Starting flow run %s on MicroVM %s.",
            run_request.payload.flow_run_id,
            run_request.microvm_id,
        )
        os.environ.update(run_request.payload.env)
        self._reply(200)
        # Submitted after the reply is written, so the fork that follows does
        # not copy this thread partway through a write.
        self.server.submit_run(run_request)

    def _read_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise InvalidRunHookPayload("Content-Length is not an integer.") from None
        if length > MAX_REQUEST_BODY_BYTES:
            raise InvalidRunHookPayload(
                f"Request body is {length} bytes; the limit is {MAX_REQUEST_BODY_BYTES}."
            )
        return self.rfile.read(length)

    def _reply(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()
        self.wfile.flush()
