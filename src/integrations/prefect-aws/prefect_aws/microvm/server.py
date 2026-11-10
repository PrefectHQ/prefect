"""HTTP server for the AWS Lambda MicroVM lifecycle hooks."""

from __future__ import annotations

import importlib
import os
import queue
import socket
import socketserver
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
HANDLER_FINISH_TIMEOUT_SECONDS = 10
WAKE_INTERVAL_SECONDS = 0.01
WAKE_CONNECT_TIMEOUT_SECONDS = 1

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
        self._handlers_finished = threading.Condition()
        self._active_handlers = 0

    def server_bind(self) -> None:
        # `HTTPServer.server_bind` names the server with `socket.getfqdn`, a reverse
        # DNS lookup that blocks startup while DNS is slow or unreachable.
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = port

    def process_request(self, request: Any, client_address: Any) -> None:
        # Counted on the serving thread, before the handler thread starts, so
        # `stop_serving` cannot miss a handler that has not started yet.
        with self._handlers_finished:
            self._active_handlers += 1
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._handler_finished()
            raise

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._handler_finished()

    def _handler_finished(self) -> None:
        with self._handlers_finished:
            self._active_handlers -= 1
            self._handlers_finished.notify_all()

    def stop_serving(self, timeout: float = HANDLER_FINISH_TIMEOUT_SECONDS) -> None:
        """
        Stop accepting hook requests and wait for the requests in progress to
        finish, so that no handler thread holds a lock when the process forks.

        Args:
            timeout: The longest time to wait for requests in progress, in seconds.
        """
        # `serve_forever` sees the shutdown request only when `select` returns; a
        # connection ends that wait, and an early one is served, so wake until
        # `shutdown` returns.
        shut_down = threading.Event()
        waker = threading.Thread(
            target=self._wake_serving_loop,
            args=(shut_down,),
            name="microvm-lifecycle-hooks-waker",
            daemon=True,
        )
        waker.start()
        try:
            self.shutdown()
        finally:
            shut_down.set()
            waker.join(timeout=WAKE_CONNECT_TIMEOUT_SECONDS + WAKE_INTERVAL_SECONDS)
            if waker.is_alive():
                logger.debug("The lifecycle hook server waker thread is still running.")
        with self._handlers_finished:
            finished = self._handlers_finished.wait_for(
                lambda: self._active_handlers == 0, timeout=timeout
            )
        if not finished:
            logger.warning(
                "%d lifecycle hook requests were still in progress after %s seconds.",
                self._active_handlers,
                timeout,
            )

    def _wake_serving_loop(self, shut_down: threading.Event) -> None:
        # The server binds the wildcard address; connect through loopback.
        loopback = ("127.0.0.1", self.server_address[1])
        while not shut_down.is_set():
            try:
                with socket.create_connection(
                    loopback, timeout=WAKE_CONNECT_TIMEOUT_SECONDS
                ):
                    pass
            except OSError:
                logger.debug(
                    "Could not wake the lifecycle hook server; it stops within "
                    "its poll interval instead.",
                    exc_info=True,
                )
                return
            shut_down.wait(WAKE_INTERVAL_SECONDS)

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
    _replied = False

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

        # Every path below submits exactly one outcome; without one,
        # `wait_for_run_request` blocks forever.
        outcome: RunHookRequest | InvalidRunHookPayload = InvalidRunHookPayload(
            "The `/run` request was interrupted."
        )
        try:
            outcome = self._start_run()
        except InvalidRunHookPayload as exc:
            logger.error("Rejected `/run` request: %s", exc)
            outcome = exc
            self._reply_if_unanswered(400)
        except Exception as exc:
            logger.exception("Could not start a flow run from the `/run` request.")
            outcome = InvalidRunHookPayload(
                f"The `/run` request failed with {type(exc).__name__}."
            )
            self._reply_if_unanswered(500)
        finally:
            self.server.submit_run(outcome)

    def _start_run(self) -> RunHookRequest:
        run_request = parse_run_hook_request(self._read_body())
        logger.info(
            "Starting flow run %s on MicroVM %s.",
            run_request.payload.flow_run_id,
            run_request.microvm_id,
        )
        os.environ.update(run_request.payload.env)
        self._reply(200)
        return run_request

    def _read_body(self) -> bytes:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            raise InvalidRunHookPayload("The request has no Content-Length.")
        try:
            length = int(content_length)
        except ValueError:
            raise InvalidRunHookPayload("Content-Length is not an integer.") from None
        if length < 0:
            raise InvalidRunHookPayload("Content-Length is negative.")
        if length > MAX_REQUEST_BODY_BYTES:
            raise InvalidRunHookPayload(
                f"Request body is {length} bytes; the limit is {MAX_REQUEST_BODY_BYTES}."
            )
        return self.rfile.read(length)

    def _reply_if_unanswered(self, status: int) -> None:
        if self._replied:
            return
        try:
            self._reply(status)
        except OSError:
            logger.warning("Could not reply %d to the `/run` request.", status)

    def _reply(self, status: int) -> None:
        self._replied = True
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()
        self.wfile.flush()
