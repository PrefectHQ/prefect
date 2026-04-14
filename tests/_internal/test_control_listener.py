"""Tests for the child-side runner control listener.

These exercise the listener with a real loopback socket on the other end so
we cover the actual byte exchange and platform-specific delivery behavior.
The fake "runner" here is just an `asyncio.start_server` we drive directly.
"""

from __future__ import annotations

import asyncio
import os
import signal
import threading
import time
from typing import AsyncIterator

import pytest

from prefect._internal import control_listener


@pytest.fixture(autouse=True)
def reset_listener_state():
    control_listener.reset_for_testing()
    # Clear env vars from any previous run
    os.environ.pop("PREFECT__CONTROL_PORT", None)
    os.environ.pop("PREFECT__CONTROL_TOKEN", None)
    yield
    control_listener.reset_for_testing()
    os.environ.pop("PREFECT__CONTROL_PORT", None)
    os.environ.pop("PREFECT__CONTROL_TOKEN", None)


@pytest.fixture
async def fake_runner_server() -> AsyncIterator[
    tuple[
        int,
        "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
    ]
]:
    """A trivial accept loop that surfaces accepted streams via a queue."""
    accepted: asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = (
        asyncio.Queue()
    )
    held_writers: list[asyncio.StreamWriter] = []
    done_events: list[asyncio.Event] = []

    async def _handle(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await reader.readline()
        except Exception:
            writer.close()
            return
        held_writers.append(writer)
        done = asyncio.Event()
        done_events.append(done)
        await accepted.put((reader, writer))
        # Park here without touching the reader so the test can drive it.
        await done.wait()

    server = await asyncio.start_server(_handle, host="127.0.0.1", port=0)
    sockets = server.sockets or []
    port = sockets[0].getsockname()[1]
    try:
        yield port, accepted
    finally:
        for done in done_events:
            done.set()
        for writer in held_writers:
            try:
                writer.close()
            except Exception:
                pass
        server.close()
        try:
            await asyncio.wait_for(server.wait_closed(), timeout=1.0)
        except (asyncio.TimeoutError, Exception):
            pass


class TestControlListener:
    def test_start_is_noop_without_env_vars(self) -> None:
        control_listener.start()
        assert control_listener.get_intent() is None

    def test_get_intent_returns_none_initially(self) -> None:
        assert control_listener.get_intent() is None

    async def test_listener_connects_to_runner(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-1234"

        control_listener.start()

        reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)
        assert reader is not None
        assert writer is not None

    async def test_intent_set_on_cancel_byte(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-2"

        # Install a custom SIGTERM handler so interrupt_main has something
        # to deliver to (rather than killing the test process).
        signal_received = threading.Event()

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: True,
            )
            if os.name != "nt":
                monkeypatch.setattr(
                    control_listener,
                    "_can_ack_control_intent",
                    lambda: True,
                )
            control_listener.start()
            control_listener.mark_signal_handler_ready()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)
            ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ready == b"r"

            # Send the cancel byte and wait for the ack.
            writer.write(b"c")
            await writer.drain()
            ack = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ack == b"a"

            # Intent flag should be set.
            assert control_listener.get_intent() == "cancel"

            for _ in range(50):
                if signal_received.is_set():
                    break
                time.sleep(0.01)
            if os.name == "nt":
                assert signal_received.is_set()
            else:
                assert not signal_received.is_set()
        finally:
            signal.signal(signal.SIGTERM, original)

    @pytest.mark.skipif(os.name == "nt", reason="uses POSIX bridge semantics")
    def test_deliver_ready_intent_posix_only_acks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert data == b"a"
                events.append("ack")

        monkeypatch.setattr(
            control_listener,
            "_can_ack_control_intent",
            lambda: True,
        )
        control_listener._stage_intent("cancel")

        assert control_listener._deliver_ready_intent(_FakeSocket()) is True

        assert events == ["ack"]
        assert control_listener.get_intent() == "cancel"

    @pytest.mark.skipif(os.name == "nt", reason="uses POSIX bridge semantics")
    def test_flush_deferred_intent_posix_only_acks(self) -> None:
        events: list[str] = []

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert data == b"a"
                events.append("ack")

        control_listener._stage_intent("cancel")

        assert control_listener._flush_deferred_intent(_FakeSocket()) is True

        assert events == ["ack"]
        assert control_listener.get_intent() == "cancel"

    def test_flush_deferred_intent_windows_drops_pending_intent_when_ack_write_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert data == b"a"
                events.append("ack-failed")
                raise OSError("socket closed")

        monkeypatch.setattr(control_listener.os, "name", "nt")
        monkeypatch.setattr(
            control_listener._thread,
            "interrupt_main",
            lambda signum: events.append("interrupt"),
        )
        control_listener._stage_intent("cancel")

        assert control_listener._flush_deferred_intent(_FakeSocket()) is False

        assert events == ["ack-failed"]
        assert control_listener.get_intent() is None

    def test_deliver_ready_intent_windows_acks_before_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert data == b"a"
                events.append("ack")

        def _fake_interrupt_main(signum: int) -> None:
            assert signum == signal.SIGTERM
            events.append("interrupt")

        monkeypatch.setattr(control_listener.os, "name", "nt")
        monkeypatch.setattr(
            control_listener,
            "_can_ack_control_intent",
            lambda: True,
        )
        monkeypatch.setattr(
            control_listener._thread, "interrupt_main", _fake_interrupt_main
        )
        control_listener._stage_intent("cancel")

        assert control_listener._deliver_ready_intent(_FakeSocket()) is True

        assert events == ["ack", "interrupt"]
        assert control_listener.get_intent() == "cancel"

    def test_deliver_ready_intent_windows_returns_false_when_bridge_is_stale(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                events.append("ack")

        monkeypatch.setattr(control_listener.os, "name", "nt")
        monkeypatch.setattr(
            control_listener,
            "_can_ack_control_intent",
            lambda: False,
        )
        monkeypatch.setattr(
            control_listener._thread,
            "interrupt_main",
            lambda signum: events.append("interrupt"),
        )
        control_listener._stage_intent("cancel")

        assert control_listener._deliver_ready_intent(_FakeSocket()) is False
        assert events == []
        assert control_listener.get_intent() is None

    async def test_ack_waits_for_signal_handler_ready(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-deferred-ack"

        signal_received = threading.Event()

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: True,
            )
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

            writer.write(b"c")
            await writer.drain()

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), timeout=0.1)

            assert control_listener.get_intent() is None
            assert not signal_received.is_set()

            control_listener.mark_signal_handler_ready()

            ready_and_ack = await asyncio.wait_for(reader.readexactly(2), timeout=2.0)
            assert ready_and_ack == b"ra"
            assert control_listener.get_intent() == "cancel"

            for _ in range(50):
                if signal_received.is_set():
                    break
                time.sleep(0.01)
            if os.name == "nt":
                assert signal_received.is_set()
            else:
                assert not signal_received.is_set()
        finally:
            signal.signal(signal.SIGTERM, original)

    async def test_ack_waits_again_after_signal_handler_is_reset(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-rearm"

        signal_received = threading.Event()

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: True,
            )
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

            control_listener.mark_signal_handler_ready()
            ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ready == b"r"

            control_listener.mark_signal_handler_not_ready()
            not_ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert not_ready == b"n"

            writer.write(b"c")
            await writer.drain()

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), timeout=0.1)

            assert control_listener.get_intent() is None
            assert not signal_received.is_set()

            control_listener.mark_signal_handler_ready()
            ready_and_ack = await asyncio.wait_for(reader.readexactly(2), timeout=2.0)
            assert ready_and_ack == b"ra"
            assert control_listener.get_intent() == "cancel"

            for _ in range(50):
                if signal_received.is_set():
                    break
                time.sleep(0.01)
            if os.name == "nt":
                assert signal_received.is_set()
            else:
                assert not signal_received.is_set()
        finally:
            signal.signal(signal.SIGTERM, original)

    async def test_ready_is_revoked_when_prefect_handler_was_replaced(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-handler-swap"

        signal_received = threading.Event()

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

            control_listener.mark_signal_handler_ready()
            ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ready == b"r"

            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: False,
            )

            writer.write(b"c")
            await writer.drain()

            not_ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert not_ready == b"n"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), timeout=0.1)

            assert control_listener.get_intent() is None
            assert not signal_received.is_set()

            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: True,
            )
            control_listener.mark_signal_handler_ready()

            ready_and_ack = await asyncio.wait_for(reader.readexactly(2), timeout=2.0)
            assert ready_and_ack == b"ra"
            assert control_listener.get_intent() == "cancel"

            for _ in range(50):
                if signal_received.is_set():
                    break
                time.sleep(0.01)
            if os.name == "nt":
                assert signal_received.is_set()
            else:
                assert not signal_received.is_set()
        finally:
            signal.signal(signal.SIGTERM, original)

    @pytest.mark.skipif(os.name == "nt", reason="uses POSIX bridge semantics")
    async def test_delivery_reverts_to_pending_if_bridge_disappears_before_queue(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-late-bridge-loss"

        signal_received = threading.Event()

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: True,
            )
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

            control_listener.mark_signal_handler_ready()
            ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ready == b"r"

            monkeypatch.setattr(
                "prefect._internal.control_listener._can_ack_control_intent",
                lambda: False,
            )

            writer.write(b"c")
            await writer.drain()

            not_ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert not_ready == b"n"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), timeout=0.1)

            assert control_listener.get_intent() is None
            assert control_listener._delivery_pending is True
            assert control_listener._delivery_completed is False
            assert control_listener._signal_handler_ready is False
            assert not signal_received.is_set()
        finally:
            signal.signal(signal.SIGTERM, original)

    async def test_windows_delivery_reverts_to_pending_if_bridge_disappears_before_interrupt(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-windows-late-bridge-loss"

        signal_received = threading.Event()

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            monkeypatch.setattr(control_listener.os, "name", "nt")
            monkeypatch.setattr(
                "prefect._internal.control_listener._prefect_sigterm_bridge_is_currently_installed",
                lambda: True,
            )
            monkeypatch.setattr(
                "prefect._internal.control_listener._can_ack_control_intent",
                lambda: False,
            )
            interrupts: list[int] = []
            monkeypatch.setattr(
                control_listener._thread,
                "interrupt_main",
                lambda signum: interrupts.append(signum),
            )
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

            control_listener.mark_signal_handler_ready()
            ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ready == b"r"

            writer.write(b"c")
            await writer.drain()

            not_ready = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert not_ready == b"n"

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(reader.read(1), timeout=0.1)

            assert control_listener.get_intent() is None
            assert control_listener._delivery_pending is True
            assert control_listener._delivery_completed is False
            assert control_listener._signal_handler_ready is False
            assert not signal_received.is_set()
            assert interrupts == []
        finally:
            signal.signal(signal.SIGTERM, original)

    async def test_unknown_intent_byte_closes_without_setting_intent(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        """An unrecognized byte on the wire should be dropped, not written
        into the intent flag. This is the forward-compatibility seam for
        future intents: a future runner that sends `b'x'` before the child
        knows about it must not corrupt the child's intent state."""
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-3"

        control_listener.start()

        reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

        writer.write(b"x")
        await writer.drain()

        # Give the reader loop a moment to process the byte and exit.
        for _ in range(50):
            if control_listener._reader_thread is not None and not (
                control_listener._reader_thread.is_alive()
            ):
                break
            await asyncio.sleep(0.01)

        assert control_listener.get_intent() is None

    def test_start_is_idempotent(
        self,
    ) -> None:
        # Without env vars, start() is a no-op and remains a no-op on second call.
        control_listener.start()
        control_listener.start()
        assert control_listener.get_intent() is None

    def test_start_handles_connect_failure_gracefully(self) -> None:
        # Use a port we know nothing is listening on. The listener should
        # silently no-op rather than raising.
        os.environ["PREFECT__CONTROL_PORT"] = "1"  # privileged, will fail
        os.environ["PREFECT__CONTROL_TOKEN"] = "anything"
        control_listener.start()
        assert control_listener.get_intent() is None

    def test_start_handles_invalid_port(self) -> None:
        os.environ["PREFECT__CONTROL_PORT"] = "not-a-number"
        os.environ["PREFECT__CONTROL_TOKEN"] = "anything"
        control_listener.start()
        assert control_listener.get_intent() is None
