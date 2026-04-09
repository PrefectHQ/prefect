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
3. When the runner wants to act on the run, it writes the intent byte over
   the socket. The reader thread looks up the corresponding
   `Intent`, sets a process-level intent flag, sends `b'a'` as an
   acknowledgement, and triggers `_thread.interrupt_main(signal.SIGTERM)`
   so the main thread's installed `SIGTERM` handler runs at the next
   bytecode boundary.
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


def _reader_loop(sock: socket.socket) -> None:
    """Block on the runner's control channel and act on the intent byte.

    Runs in a daemon thread. Exits silently on socket errors so the channel
    is best-effort and never crashes the child.
    """
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
            try:
                sock.sendall(b"a")
            except OSError:
                pass
            # Trigger the main thread's SIGTERM handler. This works on all
            # platforms because Python's signal infrastructure is
            # cross-platform; the OS-level signal is not actually
            # delivered.
            try:
                _thread.interrupt_main(signal.SIGTERM)
            except (ValueError, RuntimeError):
                # Main thread may have already exited
                pass
            return
    finally:
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
        thread.start()

        _socket = sock
        _reader_thread = thread
        _started = True


def reset_for_testing() -> None:
    """Reset module state. Tests only."""
    global _intent, _started, _socket, _reader_thread
    with _intent_lock:
        _intent = None
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
