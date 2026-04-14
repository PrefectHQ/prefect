"""
Runner-side cross-platform control channel for delivering intent into child
flow run processes.

The runner uses a TCP loopback socket to deliver a single-byte control
*intent* into child flow run processes before killing them. The child
connects back to the runner shortly after starting, validates a per-run
token, and blocks on the socket waiting for an intent byte. When the runner
wants to act on a run (today: cancel) it writes the intent byte to that
connection, waits briefly for the child's `b'a'` ack, and only then asks
the process manager to send the actual kill signal.

This separates "intent" from "trigger":

- The intent (cancel, and in a future PR suspend) travels over the
  loopback channel.
- The trigger is platform-specific:
  - On POSIX, the runner's normal `SIGTERM` remains the only trigger that
    interrupts blocking code.
  - On Windows, the child uses `_thread.interrupt_main(SIGTERM)` after
    acknowledging because the runner's external termination path does not map
    to Python's `TerminationSignal` bridge.

The channel does *not* replace the platform kill signal. For cancel, the
runner still goes through `ProcessManager.kill()` (in
`prefect.runner._process_manager`) afterwards, which sends `SIGTERM` (or
`CTRL_BREAK_EVENT` on Windows) and escalates to `SIGKILL` after a grace
period. What the channel adds is a pre-seeded intent on the child side: by
the time the child's `SIGTERM` handler runs, `control_listener.get_intent()`
already returns the pre-seeded intent, so the engine's
`except TerminationSignal` block can dispatch on it (`on_cancellation` vs
`on_crashed` today, with room for a third `"suspend"` branch in a follow-up).

Fully channel-driven graceful shutdown (removing the runner-side `SIGTERM`
entirely in favor of an acked-intent mode in `ProcessManager`) is a
separate, larger change.

The channel is loopback-only, per-token authenticated, and best-effort: if
the child never connects or never acks, `signal` returns `False` and the
runner falls through to the kill path anyway, where the engine will treat
the resulting termination as a crash — the same behavior as today for
unresponsive children.

This module is deliberately generic. The set of valid intents lives in
`prefect._internal.control_listener` as `Intent`; the wire
protocol is a single byte per intent, looked up via `_BYTE_FOR_INTENT`
below. Adding a new intent is a one-line change on each side.
"""

from __future__ import annotations

import asyncio
import secrets
import socket
import time
import uuid
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from prefect._internal.control_listener import Intent
from prefect.logging import get_logger

if TYPE_CHECKING:
    import logging


# How long to wait for the child to connect back to the control channel.
# Startup can include Python boot, imports, code pull, and flow loading, so
# this budget is intentionally longer than the steady-state ack budget.
_DEFAULT_CONNECT_TIMEOUT = 10.0
# How long to wait for the child to ack an intent byte in the common
# steady-state case where the signal bridge is already armed. Startup-time
# cancels may legally defer the final ack until `capture_sigterm()` marks
# the bridge ready. The runner distinguishes those phases explicitly via a
# child-sent readiness byte (`b"r"`): connected+ready uses this short
# timeout, while connected-but-not-ready uses the longer startup budget.
_DEFAULT_ACK_TIMEOUT = 1.0
# How long to wait for the final ack from a connected child that has not yet
# armed Prefect's signal bridge. This window can include flow loading and
# user-module imports on the `python -m prefect.engine` path, so it must be
# materially longer than the socket connect timeout.
_DEFAULT_STARTUP_ACK_TIMEOUT = 30.0


# Runner-side wire protocol: intent -> byte. Kept in sync with
# `_INTENT_FOR_BYTE` in `prefect._internal.control_listener`. Adding a new
# intent is a matched one-line change on each side.
_BYTE_FOR_INTENT: dict[Intent, bytes] = {
    "cancel": b"c",
}


@dataclass
class _Registration:
    token: str
    connected: asyncio.Event = field(default_factory=asyncio.Event)
    signal_handler_ready: asyncio.Event = field(default_factory=asyncio.Event)
    # Intent queued by `signal()` before the child connected, if any. The
    # connect handler delivers it as soon as the connection arrives.
    pending_intent: Intent | None = None
    intent_acked: asyncio.Event = field(default_factory=asyncio.Event)
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None


class ControlChannel:
    """Cross-platform IPC channel for delivering control intent to child processes.

    The runner owns one instance for its full lifetime. Each flow run subprocess
    spawned by the runner is registered before launch (via `register()`),
    which returns a port + token to inject into the child env. The child
    connects back, validates the token, and blocks waiting for an intent byte.

    Use as an async context manager. Inside the context, `port` is the
    listener's bound port (suitable for injecting into child env vars).

    The only intent exposed today is `"cancel"`. A future PR will add
    `"suspend"` by extending the `Intent` literal, the byte map, and
    the engine's `except TerminationSignal` dispatch.
    """

    def __init__(
        self,
        *,
        connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
        ack_timeout: float = _DEFAULT_ACK_TIMEOUT,
        startup_ack_timeout: float = _DEFAULT_STARTUP_ACK_TIMEOUT,
    ) -> None:
        self._connect_timeout = connect_timeout
        self._ack_timeout = ack_timeout
        self._startup_ack_timeout = startup_ack_timeout
        self._registrations: dict[uuid.UUID, _Registration] = {}
        self._tokens_to_id: dict[str, uuid.UUID] = {}
        self._server: asyncio.base_events.Server | None = None
        self._lock = asyncio.Lock()
        self._port: int | None = None
        self._exit_stack = AsyncExitStack()
        self._logger: logging.Logger = get_logger("runner.control_channel")

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError(
                "ControlChannel is not running; "
                "use `async with channel:` before reading `.port`"
            )
        return self._port

    async def __aenter__(self) -> ControlChannel:
        try:
            self._server = await asyncio.start_server(
                self._handle_connection,
                host="127.0.0.1",
                port=0,
                family=socket.AF_INET,
                backlog=128,
            )
        except OSError as exc:
            self._logger.warning(
                "Failed to bind control channel listener on loopback; "
                "falling back to kill-only cancellation. Error: %s",
                exc,
            )
            self._server = None
            self._port = None
            return self
        sockets = self._server.sockets or []
        if not sockets:
            self._logger.warning(
                "Control channel listener started without a bound socket; "
                "falling back to kill-only cancellation."
            )
            self._server.close()
            self._server = None
            self._port = None
            return self
        self._port = sockets[0].getsockname()[1]
        self._logger.debug("Control channel listening on 127.0.0.1:%s", self._port)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        # Close any lingering writer/connections first so wait_closed() below
        # can return promptly. Order matters: server.wait_closed() blocks
        # until every accepted connection drains.
        for reg in list(self._registrations.values()):
            if reg.writer is not None:
                try:
                    reg.writer.close()
                except Exception:
                    pass
        self._registrations.clear()
        self._tokens_to_id.clear()

        if self._server is not None:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=2.0)
            except (asyncio.TimeoutError, Exception):
                pass
            self._server = None
        self._port = None

    def register(self, flow_run_id: uuid.UUID) -> tuple[int, str]:
        """Reserve a token for a flow run that's about to be launched.

        Returns `(port, token)` to be injected into the child env via
        `PREFECT__CONTROL_PORT` and `PREFECT__CONTROL_TOKEN`. The token is
        single-use; subsequent registrations for the same `flow_run_id` get
        a new token (and any prior pending state is dropped).
        """
        if self._port is None:
            raise RuntimeError(
                "ControlChannel is not running; "
                "use `async with channel:` before registering"
            )
        # Drop any prior registration for this id (e.g. retry).
        prior = self._registrations.pop(flow_run_id, None)
        if prior is not None:
            self._tokens_to_id.pop(prior.token, None)
            if prior.writer is not None:
                try:
                    prior.writer.close()
                except Exception:
                    pass

        token = secrets.token_hex(16)
        self._registrations[flow_run_id] = _Registration(token=token)
        self._tokens_to_id[token] = flow_run_id
        return self._port, token

    def unregister(self, flow_run_id: uuid.UUID) -> None:
        """Drop a flow run's registration and close any associated connection."""
        reg = self._registrations.pop(flow_run_id, None)
        if reg is None:
            return
        self._tokens_to_id.pop(reg.token, None)
        if reg.writer is not None:
            try:
                reg.writer.close()
            except Exception:
                pass

    async def signal(self, flow_run_id: uuid.UUID, intent: Intent) -> bool:
        """Deliver a control intent byte to the child and wait for ack.

        Returns `True` if the child acknowledged within the timeout, `False`
        otherwise. A `False` return is a signal to the caller to fall through
        to its fallback path (for `"cancel"` that means a forced kill) — the
        engine has not been told to interpret the upcoming termination as
        anything but a crash.

        If the child has not yet connected, the intent is queued and
        delivered as soon as the connection arrives (still bounded by the
        same timeout).
        """
        reg = self._registrations.get(flow_run_id)
        if reg is None:
            self._logger.debug(
                "signal(%s) called for unregistered flow run '%s'",
                intent,
                flow_run_id,
            )
            return False

        intent_byte = _BYTE_FOR_INTENT.get(intent)
        if intent_byte is None:
            # Defensive: Intent is a Literal so this should be unreachable,
            # but a runtime-only `Intent.__args__` expansion mistake would
            # land here instead of silently writing garbage over the wire.
            self._logger.error(
                "Unknown control intent %r for flow run '%s'; ignoring.",
                intent,
                flow_run_id,
            )
            return False

        reg.pending_intent = intent

        try:
            # Wait for the child to connect, if it hasn't already.
            try:
                await asyncio.wait_for(
                    reg.connected.wait(), timeout=self._connect_timeout
                )
            except asyncio.TimeoutError:
                reg.pending_intent = None
                self._logger.debug(
                    "Child for flow run '%s' did not connect to control"
                    " channel within %.1fs",
                    flow_run_id,
                    self._connect_timeout,
                )
                return False

            # Once the child is connected, any queued startup-time intent
            # must be delivered by the active signal() call, not left armed
            # for a later connection/timeout race.
            reg.pending_intent = None
            await self._deliver_intent(reg, intent_byte)

            ack_wait_timeout = await self._wait_for_intent_ack(reg)
            if ack_wait_timeout is None:
                self._logger.debug(
                    "Child for flow run '%s' did not ack %s within %.1fs",
                    flow_run_id,
                    intent,
                    self._startup_ack_timeout
                    if not reg.signal_handler_ready.is_set()
                    else self._ack_timeout,
                )
                return False
            return True
        except Exception:
            reg.pending_intent = None
            self._logger.exception(
                "Error delivering %s intent for flow run '%s'", intent, flow_run_id
            )
            return False

    async def _wait_for_intent_ack(self, reg: _Registration) -> float | None:
        current_ready = reg.signal_handler_ready.is_set()
        current_timeout = (
            self._ack_timeout
            if current_ready
            else max(self._ack_timeout, self._startup_ack_timeout)
        )
        deadline = time.monotonic() + current_timeout

        while True:
            if reg.intent_acked.is_set():
                return current_timeout

            ready_now = reg.signal_handler_ready.is_set()
            if ready_now != current_ready:
                current_ready = ready_now
                current_timeout = (
                    self._ack_timeout
                    if current_ready
                    else max(self._ack_timeout, self._startup_ack_timeout)
                )
                deadline = time.monotonic() + current_timeout

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None

            try:
                await asyncio.wait_for(
                    reg.intent_acked.wait(), timeout=min(remaining, 0.1)
                )
            except asyncio.TimeoutError:
                continue

    async def _deliver_intent(self, reg: _Registration, intent_byte: bytes) -> None:
        if reg.writer is None:
            return
        try:
            reg.writer.write(intent_byte)
            await reg.writer.drain()
        except (ConnectionError, OSError):
            return

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Validate the incoming connection's token and bind it to a flow run."""
        try:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            except asyncio.TimeoutError:
                writer.close()
                return

            token = line.strip().decode("ascii", errors="replace")
            if not token:
                writer.close()
                return

            flow_run_id = self._tokens_to_id.get(token)
            if flow_run_id is None:
                self._logger.debug("Control channel: rejected unknown token")
                writer.close()
                return

            reg = self._registrations.get(flow_run_id)
            if reg is None:
                writer.close()
                return

            reg.reader = reader
            reg.writer = writer
            reg.connected.set()

            # If an intent was requested before the child connected, deliver
            # it immediately. Note: this can race with `signal()` if an
            # intent arrives concurrently with the child's connect — both
            # paths may write the same intent byte to the socket. That's
            # harmless: the child's reader thread acts on the first byte,
            # sets the process-global intent flag (which is sticky), acks
            # once, and returns. Any second intent byte queued behind it is
            # dropped on the floor when the reader thread exits, and the
            # engine only consults `get_intent` once at exception-handling
            # time.
            if reg.pending_intent is not None:
                pending_byte = _BYTE_FOR_INTENT.get(reg.pending_intent)
                if pending_byte is not None:
                    await self._deliver_intent(reg, pending_byte)

            # Wait for the child's readiness / ack bytes. `b'r'` means the
            # SIGTERM bridge is armed and steady-state ack timing now
            # applies; `b'n'` clears that readiness when the child unwinds
            # `capture_sigterm()` again; `b'a'` is the final cancel
            # acknowledgement once the child has seeded intent and is ready
            # for the platform-specific termination trigger.
            while True:
                try:
                    data = await reader.read(1)
                except (ConnectionError, OSError):
                    return
                if not data:
                    return
                if data == b"r":
                    reg.signal_handler_ready.set()
                    continue
                if data == b"n":
                    reg.signal_handler_ready.clear()
                    continue
                if data == b"a":
                    reg.intent_acked.set()
                    return
        except Exception:
            self._logger.exception(
                "Unexpected error handling control channel connection"
            )
            try:
                writer.close()
            except Exception:
                pass
