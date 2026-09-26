"""End-to-end test that spawns a real subprocess and exercises the full
loopback-channel cancel-intent path.

The runner-side `ControlChannel` lives in the test process. The child
is a real `subprocess.Popen` running a small Python program that:

1. Consumes control-channel bootstrap env.
2. Installs Prefect's real SIGTERM bridge via `capture_sigterm()`, which
   opens the control-channel socket.
3. Spins, waiting for SIGTERM.
4. Exits with a status code that tells the test which path was taken.

This is the highest-fidelity test for the intent-byte → termination trigger
→ `TerminationSignal` chain. Other tests cover the components in isolation;
this test guarantees they connect across a process boundary on the host's
actual Python.
"""

# Real `subprocess.Popen` is the seam under test; the event loop remains live
# because every blocking wait is replaced by async polling.

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import textwrap
from uuid import UUID, uuid4

import pytest

from prefect._internal.attempt_control import (
    CURRENT_PROTOCOL_VERSION,
    NEGOTIATION_FRAME_SIZE,
    RECEIPT_CAPABILITY,
    RECEIPT_PREFIX,
    EngineOutcomeReceipt,
    Intent,
    StateOwnershipDelegation,
    decode_receipt,
    encode_negotiation,
)
from prefect.runner._control_channel import ControlChannel, ControlSignalStatus

pytestmark = pytest.mark.clear_db

CHILD_PROGRAM = textwrap.dedent(
    """
    import os
    import sys
    import time

    from prefect._internal import control_listener
    from prefect.exceptions import TerminationSignal
    from prefect.utilities.engine import capture_sigterm

    control_listener.configure_from_env()

    try:
        with capture_sigterm():
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                time.sleep(0.05)
    except TerminationSignal:
        if control_listener.get_intent() == os.environ["EXPECTED_INTENT"]:
            sys.exit(7)
        sys.exit(8)

    sys.exit(9)
    """
)

RECEIPT_CHILD_PROGRAM = textwrap.dedent(
    """
    import sys
    from uuid import UUID

    from prefect._internal import control_listener
    from prefect._internal.attempt_control import EngineOutcomeReceipt

    control_listener.configure_from_env()
    control_listener.start()

    acknowledged = control_listener.report_engine_outcome(
        EngineOutcomeReceipt.state_reported(
            state_id=UUID("11111111-1111-1111-1111-111111111111"),
            state_type="FAILED",
            state_name="Failed",
        )
    )
    sys.exit(0 if acknowledged else 10)
    """
)

NEW_ENGINE_OLD_SUPERVISOR_PROGRAM = textwrap.dedent(
    """
    import os
    import sys
    import time
    from uuid import UUID

    from prefect._internal import control_listener
    from prefect._internal.attempt_control import EngineOutcomeReceipt
    from prefect.utilities.engine import capture_sigterm

    control_listener.configure_from_env()
    with capture_sigterm():
        acknowledged = control_listener.report_engine_outcome(
            EngineOutcomeReceipt.state_reported(
                state_id=UUID("22222222-2222-2222-2222-222222222222"),
                state_type="FAILED",
                state_name="Failed",
            )
        )

        deadline = time.monotonic() + 5
        while control_listener.get_intent() is None and time.monotonic() < deadline:
            time.sleep(0.01)

    if acknowledged:
        sys.exit(11)
    sys.exit(
        0
        if control_listener.get_intent() == os.environ["EXPECTED_INTENT"]
        else 12
    )
    """
)

OLD_ENGINE_PROGRAM = textwrap.dedent(
    """
    import os
    import socket
    import sys

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(("127.0.0.1", int(os.environ["PREFECT__CONTROL_PORT"])))
    sock.sendall(os.environ["PREFECT__CONTROL_TOKEN"].encode("ascii") + b"\\n")
    intent = sock.recv(1)
    if intent == b"c":
        sock.sendall(b"a")
        sys.exit(0)
    sys.exit(13)
    """
)

RACING_ENGINE_PROGRAM = textwrap.dedent(
    """
    import os
    import sys
    import time
    from uuid import UUID

    from prefect._internal import control_listener
    from prefect._internal.attempt_control import RECEIPT_PREFIX, EngineOutcomeReceipt
    from prefect.utilities.engine import capture_sigterm

    control_listener.configure_from_env()
    original_encode_receipt = control_listener.encode_receipt

    def coordinated_encode_receipt(receipt):
        if os.environ["RACE_ORDER"] == "intent-before-receipt-send":
            print("receipt-ready", flush=True)
            sys.stdin.readline()
        return original_encode_receipt(receipt)

    control_listener.encode_receipt = coordinated_encode_receipt
    receipt = (
        EngineOutcomeReceipt.state_reported(
            state_id=UUID("33333333-3333-3333-3333-333333333333"),
            state_type="FAILED",
            state_name="Failed",
        )
    )
    with capture_sigterm():
        acknowledged = control_listener.report_engine_outcome(receipt)

    if os.environ["RACE_ORDER"] == "receipt-recorded-first":
        print("receipt-recorded", flush=True)
        sys.stdin.readline()
        sys.exit(0 if acknowledged and control_listener.get_intent() is None else 14)
    sys.exit(
        0
        if not acknowledged
        and control_listener.get_intent() == os.environ["EXPECTED_INTENT"]
        else 15
    )
    """
)

ACK_LOSS_CHILD_PROGRAM = textwrap.dedent(
    """
    import sys
    from uuid import UUID

    from prefect._internal import control_listener
    from prefect._internal.attempt_control import EngineOutcomeReceipt

    control_listener.configure_from_env()
    control_listener.start()
    acknowledged = control_listener.report_engine_outcome(
        EngineOutcomeReceipt.state_reported(
            state_id=UUID("44444444-4444-4444-4444-444444444444"),
            state_type="FAILED",
            state_name="Failed",
        )
    )
    sys.exit(16 if acknowledged else 0)
    """
)

MALFORMED_ENGINE_PROGRAM = textwrap.dedent(
    """
    import os
    import socket
    import sys

    from prefect._internal.attempt_control import (
        CURRENT_PROTOCOL_VERSION,
        NEGOTIATION_FRAME_SIZE,
        RECEIPT_CAPABILITY,
        RECEIPT_PREFIX,
        encode_negotiation,
    )

    port = int(os.environ["PREFECT__CONTROL_PORT"])
    token = os.environ["PREFECT__CONTROL_TOKEN"]
    hello = encode_negotiation(CURRENT_PROTOCOL_VERSION, RECEIPT_CAPABILITY)

    unauthenticated = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    unauthenticated.settimeout(5)
    unauthenticated.connect(("127.0.0.1", port))
    unauthenticated.sendall(b"not-the-attempt-token\\n" + hello)
    if unauthenticated.recv(1) != b"":
        sys.exit(17)

    malformed = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    malformed.settimeout(5)
    malformed.connect(("127.0.0.1", port))
    malformed.sendall(token.encode("ascii") + b"\\n" + hello)
    response = b""
    while len(response) < NEGOTIATION_FRAME_SIZE:
        response += malformed.recv(NEGOTIATION_FRAME_SIZE - len(response))
    malformed.sendall(RECEIPT_PREFIX + (3).to_bytes(4, "big") + b"bad")
    if malformed.recv(1) != b"":
        sys.exit(18)
    sys.exit(0)
    """
)

REPLAYING_ENGINE_PROGRAM = textwrap.dedent(
    """
    import os
    import socket
    import sys
    import time

    port = int(os.environ["PREFECT__CONTROL_PORT"])
    token_line = os.environ["PREFECT__CONTROL_TOKEN"].encode("ascii") + b"\\n"

    first = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    first.settimeout(5)
    first.connect(("127.0.0.1", port))
    first.sendall(token_line)

    replay = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    replay.settimeout(5)
    replay.connect(("127.0.0.1", port))
    replay.sendall(token_line)
    if replay.recv(1) != b"":
        sys.exit(19)
    print("replay-rejected", flush=True)

    if first.recv(1) != b"c":
        sys.exit(20)
    first.sendall(b"a")
    time.sleep(0.1)
    sys.exit(0)
    """
)

UNNEGOTIATED_ENGINE_PROGRAM = textwrap.dedent(
    """
    import os
    import socket
    import sys
    from uuid import UUID

    from prefect._internal.attempt_control import EngineOutcomeReceipt, encode_receipt

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(("127.0.0.1", int(os.environ["PREFECT__CONTROL_PORT"])))
    receipt = encode_receipt(
        EngineOutcomeReceipt.state_reported(
            state_id=UUID("55555555-5555-5555-5555-555555555555"),
            state_type="FAILED",
            state_name="Failed",
        )
    )
    sock.sendall(
        os.environ["PREFECT__CONTROL_TOKEN"].encode("ascii") + b"\\n" + receipt
    )
    sys.exit(0 if sock.recv(1) == b"" else 21)
    """
)


def _start_child(
    program: str,
    *,
    port: int,
    token: str,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.Popen[bytes]:
    env = {
        **dict(os.environ),
        "PREFECT__CONTROL_PORT": str(port),
        "PREFECT__CONTROL_TOKEN": token,
        **(env_overrides or {}),
    }
    return subprocess.Popen(
        [sys.executable, "-c", program],
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


async def _wait_for_child(
    proc: subprocess.Popen[bytes],
) -> tuple[bytes, bytes]:
    for _ in range(100):
        if proc.poll() is not None:
            break
        await asyncio.sleep(0.05)
    assert proc.returncode is not None, "child did not exit in time"
    return proc.communicate(timeout=5)


def _ensure_child_stopped(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=5)


@pytest.mark.timeout(60)
@pytest.mark.parametrize("intent", ["cancel", "reschedule", "relinquish"])
async def test_acknowledged_intent_records_delegation_before_real_process_termination(
    intent: Intent,
):
    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)

        proc = _start_child(
            CHILD_PROGRAM,
            port=port,
            token=token,
            env_overrides={"EXPECTED_INTENT": intent},
        )

        try:
            # Give the child time to connect back to the channel before we
            # try to signal. The channel will queue the intent if we get
            # there first, but waiting tests the common case.
            for _ in range(50):
                if flow_run_id in channel._registrations:
                    reg = channel._registrations[flow_run_id]
                    if reg.connected.is_set():
                        break
                await asyncio.sleep(0.1)

            acked = await channel.signal(flow_run_id, intent)
            assert acked is ControlSignalStatus.ACKNOWLEDGED, (
                f"child failed to ack {intent} intent over loopback"
            )
            assert channel.get_conclusion(flow_run_id) == StateOwnershipDelegation(
                intent
            )

            if os.name != "nt":
                proc.send_signal(signal.SIGTERM)

            # The handler exits 7 when the acknowledged intent is visible.
            _stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 7, (
                f"expected exit code 7 ({intent} intent visible), got "
                f"{proc.returncode}; stderr: {stderr.decode(errors='replace')}"
            )
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)


@pytest.mark.timeout(60)
async def test_negotiates_and_acknowledges_receipt_from_real_subprocess():
    expected = EngineOutcomeReceipt.state_reported(
        state_id=UUID("11111111-1111-1111-1111-111111111111"),
        state_type="FAILED",
        state_name="Failed",
    )

    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        proc = _start_child(RECEIPT_CHILD_PROGRAM, port=port, token=token)

        try:
            stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 0, (
                f"receipt was not acknowledged; stderr: "
                f"{stderr.decode(errors='replace')}"
            )
            assert stdout == b""
            assert channel.get_conclusion(flow_run_id) == expected
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)


@pytest.mark.timeout(60)
@pytest.mark.parametrize(
    ("intent", "wire_byte"),
    [("cancel", b"c"), ("reschedule", b"r"), ("relinquish", b"q")],
)
async def test_new_engine_falls_back_to_old_supervisor_without_delaying_intent(
    intent: str, wire_byte: bytes
):
    accepted: asyncio.Future[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = (
        asyncio.Future()
    )

    async def handle_old_supervisor(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await reader.readline()
        accepted.set_result((reader, writer))

    server = await asyncio.start_server(handle_old_supervisor, host="127.0.0.1", port=0)
    port = (server.sockets or [])[0].getsockname()[1]
    proc = _start_child(
        NEW_ENGINE_OLD_SUPERVISOR_PROGRAM,
        port=port,
        token="mixed-version-token",
        env_overrides={"EXPECTED_INTENT": intent},
    )

    try:
        reader, writer = await asyncio.wait_for(accepted, timeout=5)
        hello = await asyncio.wait_for(
            reader.readexactly(NEGOTIATION_FRAME_SIZE), timeout=2
        )
        assert hello == encode_negotiation(CURRENT_PROTOCOL_VERSION, RECEIPT_CAPABILITY)

        # A version-one supervisor ignores the reserved hello and may deliver
        # control immediately, including while the child awaits negotiation.
        writer.write(wire_byte)
        await writer.drain()
        assert await asyncio.wait_for(reader.readexactly(1), timeout=2) == b"a"

        _stdout, stderr = await _wait_for_child(proc)
        assert proc.returncode == 0, stderr.decode(errors="replace")
        assert stderr == b""
    finally:
        _ensure_child_stopped(proc)
        if "writer" in locals():
            writer.close()
            await writer.wait_closed()
        server.close()
        await server.wait_closed()


@pytest.mark.timeout(60)
async def test_old_engine_retains_control_protocol_with_new_supervisor():
    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        proc = _start_child(OLD_ENGINE_PROGRAM, port=port, token=token)

        try:
            for _ in range(50):
                if channel._registrations[flow_run_id].connected.is_set():
                    break
                await asyncio.sleep(0.05)

            assert (
                await channel.signal(flow_run_id, "cancel")
                is ControlSignalStatus.ACKNOWLEDGED
            )
            _stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 0, stderr.decode(errors="replace")
            assert channel.get_conclusion(flow_run_id) == StateOwnershipDelegation(
                "cancel"
            )
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)


@pytest.mark.timeout(60)
@pytest.mark.parametrize("intent", ["cancel", "reschedule", "relinquish"])
@pytest.mark.parametrize(
    ("order", "intent_acknowledged"),
    [("receipt-recorded-first", False), ("intent-before-receipt-send", True)],
)
async def test_first_terminal_message_wins_real_process_race(
    intent: Intent, order: str, intent_acknowledged: bool
):
    receipt = EngineOutcomeReceipt.state_reported(
        state_id=UUID("33333333-3333-3333-3333-333333333333"),
        state_type="FAILED",
        state_name="Failed",
    )

    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        proc = _start_child(
            RACING_ENGINE_PROGRAM,
            port=port,
            token=token,
            env_overrides={"EXPECTED_INTENT": intent, "RACE_ORDER": order},
        )

        try:
            for _ in range(100):
                if channel._registrations[flow_run_id].negotiated_receipts:
                    break
                await asyncio.sleep(0.05)
            assert channel._registrations[flow_run_id].negotiated_receipts

            assert proc.stdout is not None
            assert proc.stdin is not None
            if order == "receipt-recorded-first":
                assert (
                    await asyncio.to_thread(proc.stdout.readline)
                    == b"receipt-recorded\n"
                )
                assert (
                    await channel.signal(flow_run_id, intent)
                    is ControlSignalStatus.ALREADY_CONCLUDED
                )
                await asyncio.to_thread(proc.stdin.write, b"continue\n")
                await asyncio.to_thread(proc.stdin.flush)
            else:
                assert (
                    await asyncio.to_thread(proc.stdout.readline) == b"receipt-ready\n"
                )
                signal_task = asyncio.create_task(channel.signal(flow_run_id, intent))
                while channel._registrations[flow_run_id].pending_intent is None:
                    await asyncio.sleep(0)
                assert await signal_task is ControlSignalStatus.ACKNOWLEDGED
                await asyncio.to_thread(proc.stdin.write, b"continue\n")
                await asyncio.to_thread(proc.stdin.flush)
            expected = (
                StateOwnershipDelegation(intent) if intent_acknowledged else receipt
            )
            assert channel.get_conclusion(flow_run_id) == expected

            _stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 0, stderr.decode(errors="replace")
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)


@pytest.mark.timeout(60)
async def test_acknowledgement_loss_does_not_create_engine_failure():
    expected = EngineOutcomeReceipt.state_reported(
        state_id=UUID("44444444-4444-4444-4444-444444444444"),
        state_type="FAILED",
        state_name="Failed",
    )
    recorded: asyncio.Future[EngineOutcomeReceipt] = asyncio.Future()

    async def drop_ack_after_recording(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await reader.readline()
            await reader.readexactly(NEGOTIATION_FRAME_SIZE)
            writer.write(
                encode_negotiation(CURRENT_PROTOCOL_VERSION, RECEIPT_CAPABILITY)
            )
            await writer.drain()
            assert await reader.readexactly(1) == RECEIPT_PREFIX
            size = int.from_bytes(await reader.readexactly(4), "big")
            recorded.set_result(decode_receipt(await reader.readexactly(size)))
        except (
            AssertionError,
            asyncio.IncompleteReadError,
            ConnectionError,
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            if not recorded.done():
                recorded.set_exception(exc)
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(
        drop_ack_after_recording, host="127.0.0.1", port=0
    )
    port = (server.sockets or [])[0].getsockname()[1]
    proc = _start_child(ACK_LOSS_CHILD_PROGRAM, port=port, token="ack-loss-token")

    try:
        assert await asyncio.wait_for(recorded, timeout=5) == expected
        _stdout, stderr = await _wait_for_child(proc)
        assert proc.returncode == 0, stderr.decode(errors="replace")
        assert b"Engine outcome receipt was not acknowledged" in stderr
        assert b"ack-loss-token" not in stderr
        assert b"44444444-4444-4444-4444-444444444444" not in stderr
    finally:
        _ensure_child_stopped(proc)
        server.close()
        await server.wait_closed()


@pytest.mark.timeout(60)
async def test_unauthenticated_and_malformed_messages_are_not_evidence(
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG, logger="prefect.runner.control_channel")
    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        proc = _start_child(MALFORMED_ENGINE_PROGRAM, port=port, token=token)

        try:
            _stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 0, stderr.decode(errors="replace")
            assert channel.get_conclusion(flow_run_id) is None
            assert "rejected unauthenticated connection" in caplog.text
            assert "malformed receipt" in caplog.text
            assert token not in caplog.text
            assert "not-the-attempt-token" not in caplog.text
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)


@pytest.mark.timeout(60)
async def test_first_authenticated_connection_consumes_token():
    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        proc = _start_child(REPLAYING_ENGINE_PROGRAM, port=port, token=token)

        try:
            for _ in range(100):
                if channel._registrations[flow_run_id].connected.is_set():
                    break
                await asyncio.sleep(0.05)
            assert channel._registrations[flow_run_id].connected.is_set()
            assert proc.stdout is not None
            assert await asyncio.to_thread(proc.stdout.readline) == b"replay-rejected\n"

            assert (
                await channel.signal(flow_run_id, "cancel")
                is ControlSignalStatus.ACKNOWLEDGED
            )
            assert channel.get_conclusion(flow_run_id) == StateOwnershipDelegation(
                "cancel"
            )
            _stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 0, stderr.decode(errors="replace")
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)


@pytest.mark.timeout(60)
async def test_unnegotiated_receipt_is_not_terminal_evidence(
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG, logger="prefect.runner.control_channel")
    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        proc = _start_child(UNNEGOTIATED_ENGINE_PROGRAM, port=port, token=token)

        try:
            _stdout, stderr = await _wait_for_child(proc)
            assert proc.returncode == 0, stderr.decode(errors="replace")
            assert channel.get_conclusion(flow_run_id) is None
            assert "unnegotiated receipt" in caplog.text
            assert token not in caplog.text
            assert "55555555-5555-5555-5555-555555555555" not in caplog.text
        finally:
            _ensure_child_stopped(proc)
            channel.unregister(flow_run_id)
