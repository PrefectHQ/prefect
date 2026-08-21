"""Runner side of the internal Attempt Control Session.

Each child authenticates over a per-attempt TCP loopback connection. The
version-one protocol delivers a single-byte control intent before the runner
kills the child. Compatible version-two peers negotiate receipt support and
may instead complete the session with one structured engine outcome receipt.
The first valid receipt or acknowledged control intent is recorded as the
attempt's immutable terminal conclusion.

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
`on_crashed`, or leaving the state alone for `"reschedule"`/`"relinquish"`).

The session is best-effort. Without terminal evidence, existing exit-code and
kill behavior remains the compatibility fallback. Tokens are consumed by the
first authenticated connection, so replay cannot replace the active child.
"""

from __future__ import annotations

import asyncio
import secrets
import socket
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from typing_extensions import Self

from prefect._internal.attempt_control import (
    BYTE_FOR_INTENT,
    CURRENT_PROTOCOL_VERSION,
    LEGACY_PROTOCOL_VERSION,
    MAX_RECEIPT_SIZE,
    NEGOTIATION_FRAME_SIZE,
    NEGOTIATION_PREFIX,
    RECEIPT_ACK,
    RECEIPT_CAPABILITY,
    RECEIPT_PREFIX,
    AttemptConclusion,
    Intent,
    StateOwnershipDelegation,
    decode_negotiation,
    decode_receipt,
    encode_negotiation,
)
from prefect.logging import get_logger

if TYPE_CHECKING:
    import logging

# How long to wait for the child to ack an intent byte once it is connected.
_DEFAULT_ACK_TIMEOUT = 1.0


class ControlSignalStatus(str, Enum):
    """Result of trying to delegate state ownership to a child process."""

    ACKNOWLEDGED = "acknowledged"
    ALREADY_CONCLUDED = "already_concluded"
    NOT_ACKNOWLEDGED = "not_acknowledged"


@dataclass
class _Registration:
    token: str
    connected: asyncio.Event = field(default_factory=asyncio.Event)
    disconnected: asyncio.Event = field(default_factory=asyncio.Event)
    intent_acked: asyncio.Event = field(default_factory=asyncio.Event)
    reader: asyncio.StreamReader | None = None
    writer: asyncio.StreamWriter | None = None
    negotiated_receipts: bool = False
    pending_intent: Intent | None = None
    conclusion: AttemptConclusion | None = None
    conclusion_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    writer_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ControlChannel:
    """Attempt-scoped IPC for control intent and negotiated outcome receipts.

    The runner owns one instance for its full lifetime. Each flow run subprocess
    spawned by the runner is registered before launch (via `register()`),
    which returns a port + token to inject into the child env. The child
    connects back, validates the token, and blocks waiting for an intent byte.

    Use as an async context manager. Inside the context, `port` is the
    listener's bound port (suitable for injecting into child env vars).

        The shared internal protocol module owns intent bytes, negotiation frames,
        receipt framing, and terminal conclusion types.
    """

    def __init__(
        self,
        *,
        ack_timeout: float = _DEFAULT_ACK_TIMEOUT,
    ) -> None:
        self._ack_timeout = ack_timeout
        self._registrations: dict[uuid.UUID, _Registration] = {}
        self._tokens_to_id: dict[str, uuid.UUID] = {}
        self._server: asyncio.base_events.Server | None = None
        self._port: int | None = None
        self._logger: logging.Logger = get_logger("runner.control_channel")

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError(
                "ControlChannel is not running; "
                "use `async with channel:` before reading `.port`"
            )
        return self._port

    async def __aenter__(self) -> Self:
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
        if not self._server.sockets:
            self._logger.warning(
                "Control channel listener started without a bound socket; "
                "falling back to kill-only cancellation."
            )
            self._server.close()
            self._server = None
            self._port = None
            return self
        self._port = self._server.sockets[0].getsockname()[1]
        self._logger.debug("Control channel listening on 127.0.0.1:%s", self._port)
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        # Close any lingering writer/connections first so wait_closed() below
        # can return promptly. Order matters: server.wait_closed() blocks
        # until every accepted connection drains.
        for reg in list(self._registrations.values()):
            if reg.writer is not None:
                reg.writer.close()
        self._registrations.clear()
        self._tokens_to_id.clear()

        if self._server is not None:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=2.0)
            except (asyncio.TimeoutError, OSError):
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
            prior_writer = prior.writer
            self._reset_connection_state(prior)
            if prior_writer is not None:
                prior_writer.close()

        token = secrets.token_hex(16)
        self._registrations[flow_run_id] = _Registration(token=token)
        self._tokens_to_id[token] = flow_run_id
        return self._port, token

    def get_conclusion(self, flow_run_id: uuid.UUID) -> AttemptConclusion | None:
        """Return the immutable terminal conclusion recorded for an attempt."""
        reg = self._registrations.get(flow_run_id)
        return reg.conclusion if reg is not None else None

    def unregister(self, flow_run_id: uuid.UUID) -> AttemptConclusion | None:
        """Close an attempt registration and return its terminal conclusion."""
        reg = self._registrations.pop(flow_run_id, None)
        if reg is None:
            return None
        self._tokens_to_id.pop(reg.token, None)
        reg_writer = reg.writer
        self._reset_connection_state(reg)
        if reg_writer is not None:
            reg_writer.close()
        return reg.conclusion

    async def signal(
        self, flow_run_id: uuid.UUID, intent: Intent
    ) -> ControlSignalStatus:
        """Deliver a control intent byte to the child and wait for ack.

        Returns `ACKNOWLEDGED` when the child accepts ownership,
        `ALREADY_CONCLUDED` when an engine receipt already won, and
        `NOT_ACKNOWLEDGED` when the caller should use its fallback path.

        If the child has not yet connected, the runner immediately falls
        through to its existing kill/crash path.
        """
        reg = self._registrations.get(flow_run_id)
        if reg is None:
            self._logger.debug(
                "signal(%s) called for unregistered flow run '%s'",
                intent,
                flow_run_id,
            )
            return ControlSignalStatus.NOT_ACKNOWLEDGED

        if reg.conclusion is not None:
            reg.intent_acked.clear()
            self._logger.debug(
                "Ignoring %s intent for flow run '%s' after terminal conclusion",
                intent,
                flow_run_id,
            )
            return ControlSignalStatus.ALREADY_CONCLUDED

        if reg.disconnected.is_set():
            reg.connected.clear()
            reg.intent_acked.clear()

        if not reg.connected.is_set():
            self._logger.debug(
                "Child for flow run '%s' has not connected to the control"
                " channel; falling back to direct %s handling.",
                flow_run_id,
                intent,
            )
            return ControlSignalStatus.NOT_ACKNOWLEDGED

        intent_byte = BYTE_FOR_INTENT.get(intent)
        if intent_byte is None:
            # Defensive: Intent is a Literal so this should be unreachable,
            # but a runtime-only `Intent.__args__` expansion mistake would
            # land here instead of silently writing garbage over the wire.
            self._logger.error(
                "Unknown control intent %r for flow run '%s'; ignoring.",
                intent,
                flow_run_id,
            )
            return ControlSignalStatus.NOT_ACKNOWLEDGED

        try:
            if not await self._deliver_intent(reg, intent, intent_byte):
                return (
                    ControlSignalStatus.ALREADY_CONCLUDED
                    if reg.conclusion is not None
                    else ControlSignalStatus.NOT_ACKNOWLEDGED
                )

            ack_wait_timeout = await self._wait_for_intent_ack(reg)
            if ack_wait_timeout is None:
                reg_writer = reg.writer
                self._reset_connection_state(reg)
                if reg_writer is not None:
                    reg_writer.close()
                self._logger.debug(
                    "Child for flow run '%s' did not ack %s within %.1fs",
                    flow_run_id,
                    intent,
                    self._ack_timeout,
                )
                return (
                    ControlSignalStatus.ALREADY_CONCLUDED
                    if reg.conclusion is not None
                    else ControlSignalStatus.NOT_ACKNOWLEDGED
                )
            return ControlSignalStatus.ACKNOWLEDGED
        except Exception:
            self._logger.exception(
                "Error delivering %s intent for flow run '%s'", intent, flow_run_id
            )
            return (
                ControlSignalStatus.ALREADY_CONCLUDED
                if reg.conclusion is not None
                else ControlSignalStatus.NOT_ACKNOWLEDGED
            )

    async def _wait_for_intent_ack(self, reg: _Registration) -> float | None:
        deadline = time.monotonic() + self._ack_timeout

        while True:
            if reg.intent_acked.is_set():
                return self._ack_timeout
            if reg.disconnected.is_set():
                return None

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None

            try:
                await asyncio.wait_for(
                    reg.intent_acked.wait(), timeout=min(remaining, 0.1)
                )
            except asyncio.TimeoutError:
                continue

    async def _deliver_intent(
        self, reg: _Registration, intent: Intent, intent_byte: bytes
    ) -> bool:
        async with reg.writer_lock:
            if (
                reg.writer is None
                or reg.conclusion is not None
                or reg.pending_intent is not None
            ):
                return False
            reg.pending_intent = intent
            try:
                reg.writer.write(intent_byte)
                await reg.writer.drain()
            except (ConnectionError, OSError):
                reg.pending_intent = None
                return False
        return True

    async def _record_conclusion(
        self, reg: _Registration, conclusion: AttemptConclusion
    ) -> bool:
        async with reg.conclusion_lock:
            if reg.conclusion is not None:
                return False
            reg.conclusion = conclusion
            return True

    def _reset_connection_state(
        self, reg: _Registration, *, clear_ack: bool = True
    ) -> None:
        reg.reader = None
        reg.writer = None
        reg.connected.clear()
        if clear_ack:
            reg.intent_acked.clear()
        reg.disconnected.set()

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Validate the incoming connection's token and bind it to a flow run."""
        reg: _Registration | None = None
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

            # Authentication consumes the token before the connection is bound.
            # Replays and connection replacement therefore cannot find it.
            flow_run_id = self._tokens_to_id.pop(token, None)
            if flow_run_id is None:
                self._logger.warning(
                    "Attempt control session rejected unauthenticated connection"
                )
                writer.close()
                return

            reg = self._registrations.get(flow_run_id)
            if reg is None:
                writer.close()
                return

            reg.reader = reader
            reg.writer = writer
            reg.disconnected.clear()
            reg.connected.set()

            # Process negotiation, a terminal receipt, or the child's final
            # acknowledgement of a control intent.
            while True:
                try:
                    data = await reader.read(1)
                except (ConnectionError, OSError):
                    return
                if not data:
                    return
                if data == b"a":
                    if reg.pending_intent is None:
                        self._logger.warning(
                            "Attempt control session received an unexpected intent acknowledgement"
                        )
                        return
                    delegation = StateOwnershipDelegation(reg.pending_intent)
                    if await self._record_conclusion(reg, delegation):
                        reg.intent_acked.set()
                        self._logger.debug(
                            "Attempt control session recorded acknowledged %s intent",
                            reg.pending_intent,
                        )
                    else:
                        self._logger.debug(
                            "Ignoring acknowledged control after terminal conclusion"
                        )
                    return
                if data == NEGOTIATION_PREFIX[:1]:
                    try:
                        remainder = await reader.readexactly(NEGOTIATION_FRAME_SIZE - 1)
                        version, capabilities = decode_negotiation(data + remainder)
                    except (asyncio.IncompleteReadError, TypeError, ValueError):
                        self._logger.warning(
                            "Attempt control session received malformed negotiation"
                        )
                        return
                    selected_version = (
                        CURRENT_PROTOCOL_VERSION
                        if version >= CURRENT_PROTOCOL_VERSION
                        and capabilities & RECEIPT_CAPABILITY
                        else LEGACY_PROTOCOL_VERSION
                    )
                    selected_capabilities = (
                        RECEIPT_CAPABILITY
                        if selected_version == CURRENT_PROTOCOL_VERSION
                        else 0
                    )
                    reg.negotiated_receipts = bool(selected_capabilities)
                    async with reg.writer_lock:
                        writer.write(
                            encode_negotiation(selected_version, selected_capabilities)
                        )
                        await writer.drain()
                    self._logger.debug(
                        "Attempt control negotiation selected protocol %d with receipt support %s",
                        selected_version,
                        reg.negotiated_receipts,
                    )
                    continue
                if data == RECEIPT_PREFIX:
                    if not reg.negotiated_receipts:
                        self._logger.warning(
                            "Attempt control session received an unnegotiated receipt"
                        )
                        return
                    try:
                        size = int.from_bytes(await reader.readexactly(4), "big")
                        if size > MAX_RECEIPT_SIZE:
                            raise ValueError("Receipt payload is too large")
                        receipt = decode_receipt(await reader.readexactly(size))
                    except (asyncio.IncompleteReadError, ValueError):
                        self._logger.warning(
                            "Attempt control session received a malformed receipt"
                        )
                        return
                    if await self._record_conclusion(reg, receipt):
                        self._logger.debug(
                            "Attempt control session recorded engine outcome receipt"
                        )
                        async with reg.writer_lock:
                            writer.write(RECEIPT_ACK)
                            await writer.drain()
                    else:
                        self._logger.debug("Ignoring receipt after terminal conclusion")
                    return
                self._logger.warning(
                    "Attempt control session received a malformed message"
                )
                return
        except Exception:
            self._logger.exception(
                "Unexpected error handling control channel connection"
            )
            writer.close()
        finally:
            if reg is not None:
                writer.close()
                self._reset_connection_state(reg, clear_ack=False)
