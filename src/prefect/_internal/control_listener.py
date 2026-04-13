"""
Child-process runner-control intent listener.

When a flow run is launched in a subprocess by the runner, the runner needs
a way to tell the child "this termination has a specific intent" so the
child engine can dispatch on it (today: cancel → `on_cancellation` hooks
instead of `on_crashed` hooks; future: suspend → persisting pause state).

The runner uses a TCP loopback channel for that signal:

1. Before launching the child, the runner registers the flow run with its
   `ControlChannel` (in `prefect.runner._control_channel`) and injects
   `PREFECT__CONTROL_PORT` and `PREFECT__CONTROL_TOKEN` into the child env.
2. The child calls `start()` early at process entry. `start` connects
   back to `127.0.0.1:PORT`, sends the token, and spawns a daemon thread
   that blocks on the socket waiting for a single intent byte.
   Once `capture_sigterm()` installs Prefect's SIGTERM handler, the child
   proactively sends `b'r'` to tell the runner that the signal bridge is
   armed and steady-state ack timing is now safe. When that handler is
   later removed, the child sends `b'n'` so the runner stops treating the
   process as ready.
3. When the runner wants to act on the run, it writes the intent byte over
   the socket. The reader thread looks up the corresponding
   `Intent`, seeds a process-level intent flag immediately, and then waits
   until `capture_sigterm()` has installed Prefect's SIGTERM handler before
   sending `b'a'` back to the runner and triggering
   `_thread.interrupt_main(signal.SIGTERM)`. This prevents startup-time
   cancellations from being acked before the engine can actually consume the
   synthetic signal.
4. The signal handler raises `TerminationSignal`. The engine's
   `except TerminationSignal` block then reads `get_intent()` at
   exception-handling time and dispatches on it. The intent is *not*
   propagated via a ContextVar — it is a process-global module flag,
   which is exactly why nested subflows running in the same process
   inherit the outcome correctly without any extra plumbing.

This module deliberately uses a daemon thread + a synchronous socket so
the intent flag can be read from a signal handler without touching an
event loop or performing API calls in signal context. The listener is a
no-op when the env vars are absent (e.g. when running outside the runner).

The intent flag is process-global by design: one runner subprocess hosts
one top-level flow tree, and every nested subflow in that interpreter
shares the same intent. This module does not generalize to multiple
independent flow trees in one interpreter — that is an intentional
invariant, not a gap to be filled.

The set of valid intents lives in `Intent` below. Only `"cancel"`
is defined today; a follow-up PR will add `"suspend"` by extending the
literal, adding a byte mapping, and giving the engine a new dispatch
branch. The wire protocol, IPC transport, and start/ack plumbing are
already generic — a future intent does not need this module restructured.
"""

from __future__ import annotations

import _thread
import os
import signal
import socket
import threading
from typing import Literal

# Valid control intents. Extend this literal to add new intents (e.g.
# `"suspend"`). Extending it requires a matching entry in
# `_INTENT_FOR_BYTE` below and in `_BYTE_FOR_INTENT` in
# `prefect.runner._control_channel`, plus a new dispatch branch in
# the engine's `except TerminationSignal` handler.
Intent = Literal["cancel"]


# Child-side wire protocol: byte -> intent. Kept in sync with
# `_BYTE_FOR_INTENT` in `prefect.runner._control_channel`. Unknown bytes
# on the wire are ignored (the reader loop falls through and returns).
_INTENT_FOR_BYTE: dict[bytes, Intent] = {
    b"c": "cancel",
}


# Process-global control intent. Set exactly once by `_reader_loop` when
# it receives a recognized intent byte from the runner, and never cleared
# in production code (only `reset_for_testing` clears it). Engines that
# consult `get_intent` should treat any non-None value as terminal: the
# listener triggers `interrupt_main(SIGTERM)` immediately after setting
# this flag, so by the time anything reads it the process is already on
# its way down. The "set exactly once per process" invariant is what
# makes it safe for `capture_sigterm` to swallow the original SIGTERM
# handler when intent is non-None (see `prefect.utilities.engine`).
_intent: Intent | None = None
_intent_lock = threading.Lock()
_started: bool = False
_started_lock = threading.Lock()
_signal_handler_ready: bool = False
_ready_notified: bool = False
_delivery_pending: bool = False
_delivery_completed: bool = False
_delivery_lock = threading.Lock()
_socket: socket.socket | None = None
_reader_thread: threading.Thread | None = None


def get_intent() -> Intent | None:
    """Return the current control intent, if any.

    Safe to call from a signal handler — only reads a module-level variable
    under a quick lock.
    """
    with _intent_lock:
        return _intent


def _set_intent(value: Intent) -> None:
    global _intent
    with _intent_lock:
        _intent = value


def _ack_and_interrupt(sock: socket.socket) -> None:
    try:
        sock.sendall(b"a")
    except OSError:
        pass
    # Trigger the main thread's SIGTERM handler. This works on all
    # platforms because Python's signal infrastructure is cross-platform;
    # the OS-level signal is not actually delivered.
    try:
        _thread.interrupt_main(signal.SIGTERM)
    except (ValueError, RuntimeError):
        # Main thread may have already exited
        pass


def _notify_ready(sock: socket.socket) -> None:
    try:
        sock.sendall(b"r")
    except OSError:
        pass


def _notify_not_ready(sock: socket.socket) -> None:
    try:
        sock.sendall(b"n")
    except OSError:
        pass


def _prefect_sigterm_bridge_is_currently_installed() -> bool:
    from prefect.utilities.engine import is_prefect_sigterm_handler_installed

    return is_prefect_sigterm_handler_installed()


def mark_signal_handler_ready() -> None:
    """Arm delivery once Prefect's SIGTERM handler is installed.

    Called by `prefect.utilities.engine.capture_sigterm()` after it
    installs the `TerminationSignal` bridge. If a control intent arrived
    during process startup, this flushes the deferred ack and synthetic
    SIGTERM immediately.
    """

    global _signal_handler_ready, _ready_notified
    global _delivery_pending, _delivery_completed

    ready_sock: socket.socket | None = None
    delivery_sock: socket.socket | None = None
    should_notify_ready = False
    with _delivery_lock:
        _signal_handler_ready = True
        if not _ready_notified:
            _ready_notified = True
            should_notify_ready = True
            ready_sock = _socket
        if _delivery_pending and not _delivery_completed:
            _delivery_pending = False
            _delivery_completed = True
            delivery_sock = _socket

    if should_notify_ready and ready_sock is not None:
        _notify_ready(ready_sock)
    if delivery_sock is not None:
        _ack_and_interrupt(delivery_sock)


def mark_signal_handler_not_ready() -> None:
    """Clear readiness when Prefect's SIGTERM handler is no longer installed."""

    global _signal_handler_ready, _ready_notified

    notify_sock: socket.socket | None = None
    should_notify_not_ready = False
    with _delivery_lock:
        if _ready_notified:
            should_notify_not_ready = True
            notify_sock = _socket
        _signal_handler_ready = False
        _ready_notified = False

    if should_notify_not_ready and notify_sock is not None:
        _notify_not_ready(notify_sock)


def _reader_loop(sock: socket.socket) -> None:
    """Block on the runner's control channel and act on the intent byte.

    Runs in a daemon thread. Exits silently on socket errors so the channel
    is best-effort and never crashes the child.
    """
    global _delivery_pending, _delivery_completed
    global _signal_handler_ready, _ready_notified

    keep_socket_open = False
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
                # Unknown byte on the wire. Strict protocol: drop the
                # connection rather than guess — the runner won't have
                # ack'd yet, so it'll treat us as unresponsive and fall
                # through to its own fallback path.
                return
            _set_intent(intent)
            deliver_now = False
            notify_not_ready = False
            with _delivery_lock:
                if not _delivery_completed:
                    if _signal_handler_ready:
                        if _prefect_sigterm_bridge_is_currently_installed():
                            _delivery_completed = True
                            deliver_now = True
                        else:
                            _signal_handler_ready = False
                            _ready_notified = False
                            _delivery_pending = True
                            notify_not_ready = True
                            keep_socket_open = True
                    else:
                        _delivery_pending = True
                        keep_socket_open = True
            if notify_not_ready:
                _notify_not_ready(sock)
            if deliver_now:
                _ack_and_interrupt(sock)
            return
    finally:
        if not keep_socket_open:
            try:
                sock.close()
            except OSError:
                pass


def start() -> None:
    """Connect to the runner's control channel if env vars are present.

    Idempotent — calling multiple times is a no-op after the first successful
    start. Safe to call from any process: a missing port/token means we're not
    running under a runner and the listener stays disabled.
    """
    global _started, _socket, _reader_thread

    with _started_lock:
        if _started:
            return

        port_str = os.environ.pop("PREFECT__CONTROL_PORT", None)
        token = os.environ.pop("PREFECT__CONTROL_TOKEN", None)
        if not port_str or not token:
            return

        try:
            port = int(port_str)
        except ValueError:
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", port))
            sock.sendall(token.encode("ascii") + b"\n")
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


def reset_for_testing() -> None:
    """Reset module state. Tests only."""
    global _intent, _started, _socket, _reader_thread
    global _signal_handler_ready, _ready_notified
    global _delivery_pending, _delivery_completed
    with _intent_lock:
        _intent = None
    with _delivery_lock:
        _signal_handler_ready = False
        _ready_notified = False
        _delivery_pending = False
        _delivery_completed = False
    with _started_lock:
        if _socket is not None:
            try:
                _socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                _socket.close()
            except OSError:
                pass
        _socket = None
        _reader_thread = None
        _started = False
