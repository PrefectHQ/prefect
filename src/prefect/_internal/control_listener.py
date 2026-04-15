"""
Child-process runner-control intent listener.

This module is intentionally small. It only supports steady-state graceful
control delivery after Prefect has already installed its SIGTERM bridge via
`capture_sigterm()`.

Protocol:

1. The runner injects `PREFECT__CONTROL_PORT` and `PREFECT__CONTROL_TOKEN`
   into the child environment.
2. Process entrypoints call `configure_from_env()` early to consume those
   one-shot env vars without connecting yet.
3. The outermost `capture_sigterm()` calls `start()`, which connects back to
   the runner and spawns a daemon thread blocked on the socket.
4. The runner writes a single-byte intent (`b"c"` today).
5. If Prefect still owns the live SIGTERM bridge, the child writes `b"a"`,
   commits the intent for engine dispatch, and on Windows triggers
   `_thread.interrupt_main(SIGTERM)`.
6. The runner then sends its normal external termination signal. On POSIX,
   that real `SIGTERM` is the only trigger that interrupts blocking code.

If the child is not connected yet, or can no longer safely acknowledge the
intent, the runner sees no ack and falls back to its existing crash-style
termination path. There is deliberately no startup-time graceful cancellation
contract in this implementation.
"""

from __future__ import annotations

import _thread
import os
import signal
import socket
import threading
from typing import Literal

Intent = Literal["cancel"]

_INTENT_FOR_BYTE: dict[bytes, Intent] = {
    b"c": "cancel",
}

_intent: Intent | None = None
_intent_lock = threading.Lock()

_configured = False
_configured_port: int | None = None
_configured_token: str | None = None

_started = False
_started_lock = threading.Lock()
_socket: socket.socket | None = None
_reader_thread: threading.Thread | None = None


def get_intent() -> Intent | None:
    """Return the committed control intent, if any."""
    with _intent_lock:
        return _intent


def _set_intent(value: Intent) -> None:
    global _intent
    with _intent_lock:
        _intent = value


def _clear_intent() -> None:
    global _intent
    with _intent_lock:
        _intent = None


def clear_intent() -> None:
    """Clear the committed control intent after the current session consumes it."""
    _clear_intent()


def configure_from_env() -> None:
    """Consume one-shot control-channel env vars without connecting yet."""
    global _configured, _configured_port, _configured_token

    with _started_lock:
        if _configured:
            return

        _configured = True
        port_str = os.environ.pop("PREFECT__CONTROL_PORT", None)
        token = os.environ.pop("PREFECT__CONTROL_TOKEN", None)
        if not port_str or not token:
            return

        try:
            _configured_port = int(port_str)
        except ValueError:
            _configured_port = None
            _configured_token = None
            return

        _configured_token = token


def _acknowledge_intent(sock: socket.socket, intent: Intent) -> bool:
    """Commit intent and acknowledge it to the runner."""
    from prefect.utilities.engine import commit_control_intent_and_ack

    if not commit_control_intent_and_ack(
        commit_intent=lambda: _set_intent(intent),
        clear_intent=_clear_intent,
        send_ack=lambda: sock.sendall(b"a"),
        trigger_cancel=(
            (lambda: _thread.interrupt_main(signal.SIGTERM))
            if os.name == "nt"
            else None
        ),
    ):
        return False

    return True


def _reader_loop(sock: socket.socket) -> None:
    """Block on the runner's control channel and act on a single intent byte."""
    try:
        while True:
            try:
                data = sock.recv(1)
            except OSError:
                return
            if not data:
                return

            intent = _INTENT_FOR_BYTE.get(data)
            if intent is None:
                return

            _acknowledge_intent(sock, intent)
            return
    finally:
        try:
            sock.close()
        except OSError:
            pass


def start() -> None:
    """Connect to the runner's control channel if bootstrap config is present."""
    global _started, _socket, _reader_thread

    configure_from_env()

    with _started_lock:
        if _started:
            return
        if _configured_port is None or _configured_token is None:
            return

        # A new listener session must not inherit a committed intent from an
        # earlier flow run in the same interpreter.
        _clear_intent()

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", _configured_port))
            sock.sendall(_configured_token.encode("ascii") + b"\n")
        except OSError:
            try:
                sock.close()
            except (OSError, UnboundLocalError):
                pass
            return

        thread = threading.Thread(
            target=_reader_loop,
            args=(sock,),
            name="prefect-control-listener",
            daemon=True,
        )
        _socket = sock
        _reader_thread = thread
        _started = True
        thread.start()


def stop() -> None:
    """Close the active control connection, if any."""
    global _configured, _configured_port, _configured_token
    global _started, _socket, _reader_thread

    with _started_lock:
        sock = _socket
        _socket = None
        _reader_thread = None
        _started = False
        _configured = False
        _configured_port = None
        _configured_token = None

    if sock is not None:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


def reset_for_testing() -> None:
    """Reset module state. Tests only."""
    global _intent, _configured, _configured_port, _configured_token

    with _intent_lock:
        _intent = None

    stop()

    with _started_lock:
        _configured = False
        _configured_port = None
        _configured_token = None
