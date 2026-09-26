"""
Child side of the internal Attempt Control Session.

This module is intentionally small. It only supports steady-state graceful
control delivery after Prefect has already installed its SIGTERM bridge via
`capture_sigterm()`.

The version-one protocol remains intact: the supervisor sends one-byte control
intents and the child acknowledges a committed intent with `b"a"`. Version-two
peers additionally negotiate outcome receipts over the same authenticated,
full-duplex loopback connection.

Session outline:

1. The runner injects `PREFECT__CONTROL_PORT` and `PREFECT__CONTROL_TOKEN`
   into the child environment.
2. Process entrypoints call `configure_from_env()` early to consume those
   one-shot env vars without connecting yet.
3. The outermost `capture_sigterm()` calls `start()`, which connects back to
   the runner and spawns a daemon thread blocked on the socket.
4. The child sends a reserved negotiation hello. A version-one supervisor
   ignores it; a version-two supervisor selects the protocol and capabilities.
5. The first terminal exchange is either an existing control intent plus
   `b"a"`, or a structured engine outcome receipt plus a receipt ack.
6. For control, the runner then sends its normal external termination signal.
   On POSIX, that real `SIGTERM` remains the only trigger that interrupts
   blocking code.

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
import time

from prefect._internal.attempt_control import (
    CURRENT_PROTOCOL_VERSION,
    INTENT_FOR_BYTE,
    NEGOTIATION_FRAME_SIZE,
    NEGOTIATION_PREFIX,
    RECEIPT_ACK,
    RECEIPT_CAPABILITY,
    EngineOutcomeReceipt,
    Intent,
    decode_negotiation,
    encode_negotiation,
    encode_receipt,
)
from prefect.logging import get_logger
from prefect.utilities.engine import commit_control_intent_and_ack

_NEGOTIATION_PROBE_TIMEOUT = 0.25
_NEGOTIATION_RESPONSE_TIMEOUT = 1.0
_RECEIPT_ACK_TIMEOUT = 1.0

_logger = get_logger(__name__)

_intent: Intent | None = None
_intent_lock = threading.Lock()

_configured = False
_configured_port: int | None = None
_configured_token: str | None = None

_started = False
_started_lock = threading.Lock()
_owner_thread_id: int | None = None
_socket: socket.socket | None = None
_reader_thread: threading.Thread | None = None
_send_lock = threading.Lock()
_negotiation_complete = threading.Event()
_negotiation_deadline: float | None = None
_receipt_acked = threading.Event()
_receipt_capable = False
_terminal_lock = threading.Lock()
_terminal_claimed = False
_receipt_in_flight = False
_outcome_report_started = False
_engine_outcome_handled = False


def get_intent() -> Intent | None:
    """Return the committed control intent, if any."""
    with _intent_lock:
        return _intent


def engine_outcome_is_handled() -> bool:
    """Return whether the engine concluded the current execution attempt."""
    return _engine_outcome_handled


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
    global _configured, _configured_port, _configured_token, _engine_outcome_handled

    with _started_lock:
        if _configured:
            return

        _configured = True
        _engine_outcome_handled = False
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
    return commit_control_intent_and_ack(
        commit_intent=lambda: _set_intent(intent),
        clear_intent=_clear_intent,
        send_ack=lambda: sock.sendall(b"a"),
        trigger_cancel=(
            (lambda: _thread.interrupt_main(signal.SIGTERM))
            if os.name == "nt"
            else None
        ),
    )


def _send(sock: socket.socket, data: bytes) -> None:
    with _send_lock:
        sock.sendall(data)


def _recv_exactly(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise OSError("Control session closed")
        chunks.extend(chunk)
    return bytes(chunks)


def _receive_negotiation_response(sock: socket.socket, first: bytes) -> None:
    """Apply one complete negotiation response from the supervisor."""
    global _receipt_capable

    response = first + _recv_exactly(sock, NEGOTIATION_FRAME_SIZE - 1)
    version, capabilities = decode_negotiation(response)
    _receipt_capable = (
        version == CURRENT_PROTOCOL_VERSION and capabilities & RECEIPT_CAPABILITY != 0
    )
    _negotiation_complete.set()
    _logger.debug(
        "Attempt control negotiation selected protocol %d with receipt support %s",
        version,
        _receipt_capable,
    )


def _handle_intent_byte(sock: socket.socket, data: bytes) -> bool | None:
    """Handle an intent, returning whether the reader should close the session."""
    global _terminal_claimed

    intent = INTENT_FOR_BYTE.get(data)
    if intent is None:
        return None

    # Serialize terminal writes so the wire order matches the local decision:
    # an intent that claims this lock before receipt transmission wins, while
    # an already-transmitted receipt remains authoritative.
    with _send_lock, _terminal_lock:
        if _terminal_claimed or _receipt_in_flight:
            _logger.debug(
                "Ignoring control intent after a terminal exchange has started"
            )
            return False
        if _acknowledge_intent(sock, intent):
            _terminal_claimed = True
        return True


def _reader_loop(sock: socket.socket) -> None:
    """Negotiate receipt support, then handle session responses and intent."""
    global _receipt_capable

    negotiation_pending = True
    try:
        first = b""
        try:
            _send(
                sock,
                encode_negotiation(CURRENT_PROTOCOL_VERSION, RECEIPT_CAPABILITY),
            )
            sock.settimeout(_NEGOTIATION_PROBE_TIMEOUT)
            first = sock.recv(1)
            if not first:
                return
            intent_handled = _handle_intent_byte(sock, first)
            if intent_handled is not None:
                if intent_handled:
                    return
                first = b""
            if first != NEGOTIATION_PREFIX[:1]:
                _logger.warning("Attempt control negotiation response was malformed")
                return
            _receive_negotiation_response(sock, first)
            negotiation_pending = False
        except TimeoutError:
            if first:
                _logger.warning("Attempt control negotiation response was malformed")
            # A version-one supervisor sends no response to the reserved hello.
            # Keep accepting a late response so scheduler latency does not
            # permanently downgrade a version-two peer.
            _receipt_capable = False
        except OSError:
            # The owning context may close the socket while negotiation is blocked.
            return
        except ValueError:
            _logger.warning("Attempt control negotiation response was malformed")
            return
        finally:
            try:
                sock.settimeout(None)
            except OSError:
                pass

        while True:
            try:
                data = sock.recv(1)
            except OSError:
                return
            if not data:
                return
            intent_handled = _handle_intent_byte(sock, data)
            if intent_handled is not None:
                if intent_handled:
                    return
                continue
            if data == NEGOTIATION_PREFIX[:1] and negotiation_pending:
                try:
                    _receive_negotiation_response(sock, data)
                except OSError:
                    return
                except ValueError:
                    _logger.warning(
                        "Attempt control negotiation response was malformed"
                    )
                    return
                negotiation_pending = False
                continue
            if data == RECEIPT_ACK:
                global _receipt_in_flight, _terminal_claimed
                with _terminal_lock:
                    if not _receipt_in_flight:
                        _logger.debug(
                            "Ignoring receipt acknowledgement after terminal exchange"
                        )
                        continue
                    _receipt_in_flight = False
                    _terminal_claimed = True
                    _receipt_acked.set()
                return
            _logger.warning("Attempt control session received a malformed message")
            return
    finally:
        _negotiation_complete.set()
        try:
            sock.close()
        except OSError:
            pass


def report_engine_outcome(receipt: EngineOutcomeReceipt) -> bool:
    """Send one negotiated outcome receipt without changing engine semantics."""
    global _outcome_report_started, _receipt_in_flight, _engine_outcome_handled

    if _owner_thread_id is not None and threading.get_ident() != _owner_thread_id:
        _logger.debug(
            "Ignoring engine outcome from a thread that does not own the control session"
        )
        return False

    # The immediate first-party engine process treats a concluded attempt as
    # successful infrastructure execution even when its supervisor cannot
    # negotiate or acknowledge the optional receipt transport.
    _engine_outcome_handled = True

    sock = _socket
    if sock is None:
        return False

    negotiation_deadline = _negotiation_deadline
    if negotiation_deadline is not None:
        _negotiation_complete.wait(max(0.0, negotiation_deadline - time.monotonic()))
    if not _receipt_capable:
        return False

    try:
        encoded_receipt = encode_receipt(receipt)
    except ValueError:
        _logger.warning("Failed to encode engine outcome receipt")
        return False

    try:
        with _send_lock, _terminal_lock:
            if _terminal_claimed or _outcome_report_started:
                return False
            _outcome_report_started = True
            _receipt_in_flight = True
            _receipt_acked.clear()
            sock.sendall(encoded_receipt)
    except OSError:
        with _terminal_lock:
            _receipt_in_flight = False
        _logger.warning("Failed to send engine outcome receipt")
        return False

    if _receipt_acked.wait(_RECEIPT_ACK_TIMEOUT):
        return True

    with _terminal_lock:
        _receipt_in_flight = False
    _logger.warning("Engine outcome receipt was not acknowledged")
    return False


def start() -> None:
    """Connect to the runner's control channel if bootstrap config is present."""
    global _started, _owner_thread_id, _socket, _reader_thread, _receipt_capable
    global _terminal_claimed, _receipt_in_flight, _outcome_report_started
    global _negotiation_deadline

    configure_from_env()

    with _started_lock:
        if _started:
            return
        if _configured_port is None or _configured_token is None:
            return

        # A new listener session must not inherit a committed intent from an
        # earlier flow run in the same interpreter.
        _clear_intent()
        _negotiation_complete.clear()
        _negotiation_deadline = None
        _receipt_acked.clear()
        _receipt_capable = False
        with _terminal_lock:
            _terminal_claimed = False
            _receipt_in_flight = False
            _outcome_report_started = False

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
        _owner_thread_id = threading.get_ident()
        _negotiation_deadline = time.monotonic() + _NEGOTIATION_RESPONSE_TIMEOUT
        _started = True
        thread.start()


def stop() -> None:
    """Close the active control connection, if any."""
    global _configured, _configured_port, _configured_token
    global _started, _owner_thread_id, _socket, _reader_thread, _receipt_capable
    global _terminal_claimed, _receipt_in_flight, _outcome_report_started
    global _negotiation_deadline

    with _started_lock:
        sock = _socket
        _socket = None
        _reader_thread = None
        _owner_thread_id = None
        _started = False
        _configured = False
        _configured_port = None
        _configured_token = None
        _receipt_capable = False
        _negotiation_complete.clear()
        _negotiation_deadline = None
        _receipt_acked.clear()
        with _terminal_lock:
            _terminal_claimed = False
            _receipt_in_flight = False
            _outcome_report_started = False

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
    global _engine_outcome_handled

    with _intent_lock:
        _intent = None

    stop()

    with _started_lock:
        _configured = False
        _configured_port = None
        _configured_token = None
        _engine_outcome_handled = False
