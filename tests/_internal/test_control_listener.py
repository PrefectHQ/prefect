"""Tests for the child-side runner control listener."""

from __future__ import annotations

import asyncio
import os
import signal
import threading
import time
from typing import AsyncIterator

import pytest

import prefect.utilities.engine as engine_utils
from prefect._internal import control_listener


@pytest.fixture(autouse=True)
def reset_listener_state():
    control_listener.reset_for_testing()
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

    async def test_configure_from_env_consumes_env_and_defers_connection(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-bootstrap"

        control_listener.configure_from_env()

        assert "PREFECT__CONTROL_PORT" not in os.environ
        assert "PREFECT__CONTROL_TOKEN" not in os.environ

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(accepted.get(), timeout=0.1)

        control_listener.start()
        reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)
        assert reader is not None
        assert writer is not None

    async def test_start_is_idempotent(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-idempotent"

        control_listener.start()
        control_listener.start()

        await asyncio.wait_for(accepted.get(), timeout=2.0)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(accepted.get(), timeout=0.1)

    async def test_listener_connects_to_runner(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-connect"

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
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-cancel"

        signal_received = threading.Event()

        def _commit_and_ack(
            commit_intent, clear_intent, send_ack, trigger_cancel=None
        ) -> bool:
            commit_intent()
            send_ack()
            if trigger_cancel is not None:
                trigger_cancel()
            return True

        def _handler(signum, frame):
            signal_received.set()

        original = signal.signal(signal.SIGTERM, _handler)
        try:
            monkeypatch.setattr(
                engine_utils, "commit_control_intent_and_ack", _commit_and_ack
            )
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)
            writer.write(b"c")
            await writer.drain()

            ack = await asyncio.wait_for(reader.readexactly(1), timeout=2.0)
            assert ack == b"a"
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

    def test_acknowledge_intent_windows_acks_before_interrupt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []

        def _commit_and_ack(
            commit_intent, clear_intent, send_ack, trigger_cancel=None
        ) -> bool:
            commit_intent()
            send_ack()
            if trigger_cancel is not None:
                trigger_cancel()
            return True

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert data == b"a"
                events.append("ack")

        monkeypatch.setattr(control_listener.os, "name", "nt")
        monkeypatch.setattr(
            engine_utils, "commit_control_intent_and_ack", _commit_and_ack
        )
        monkeypatch.setattr(
            control_listener._thread,
            "interrupt_main",
            lambda signum: events.append(f"interrupt:{signum}"),
        )

        assert control_listener._acknowledge_intent(_FakeSocket(), "cancel") is True
        assert control_listener.get_intent() == "cancel"
        assert events == ["ack", f"interrupt:{signal.SIGTERM}"]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX-specific ack ordering")
    def test_acknowledge_intent_commits_before_ack_write(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        observed_intents: list[str | None] = []

        def _commit_and_ack(
            commit_intent, clear_intent, send_ack, trigger_cancel=None
        ) -> bool:
            commit_intent()
            send_ack()
            if trigger_cancel is not None:
                trigger_cancel()
            return True

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert data == b"a"
                observed_intents.append(control_listener.get_intent())

        monkeypatch.setattr(
            engine_utils, "commit_control_intent_and_ack", _commit_and_ack
        )

        assert control_listener._acknowledge_intent(_FakeSocket(), "cancel") is True
        assert observed_intents == ["cancel"]
        assert control_listener.get_intent() == "cancel"

    async def test_listener_does_not_ack_when_bridge_is_unavailable(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-stale-bridge"

        monkeypatch.setattr(
            engine_utils,
            "commit_control_intent_and_ack",
            lambda commit_intent, clear_intent, send_ack, trigger_cancel=None: False,
        )
        control_listener.start()

        reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)
        writer.write(b"c")
        await writer.drain()

        data = await asyncio.wait_for(reader.read(1), timeout=2.0)
        assert data == b""
        assert control_listener.get_intent() is None

    def test_acknowledge_intent_drops_intent_when_ack_write_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _commit_and_ack(
            commit_intent, clear_intent, send_ack, trigger_cancel=None
        ) -> bool:
            commit_intent()
            try:
                send_ack()
            except OSError:
                clear_intent()
                return False
            if trigger_cancel is not None:
                trigger_cancel()
            return True

        class _FakeSocket:
            def sendall(self, data: bytes) -> None:
                assert control_listener.get_intent() == "cancel"
                raise OSError("socket closed")

        monkeypatch.setattr(
            engine_utils, "commit_control_intent_and_ack", _commit_and_ack
        )

        assert control_listener._acknowledge_intent(_FakeSocket(), "cancel") is False
        assert control_listener.get_intent() is None

    async def test_start_clears_stale_intent_from_prior_session(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-new-session"

        control_listener._set_intent("cancel")
        control_listener.start()

        await asyncio.wait_for(accepted.get(), timeout=2.0)
        assert control_listener.get_intent() is None

    async def test_unknown_intent_byte_closes_without_setting_intent(
        self,
        fake_runner_server: tuple[
            int,
            "asyncio.Queue[tuple[asyncio.StreamReader, asyncio.StreamWriter]]",
        ],
    ) -> None:
        port, accepted = fake_runner_server
        os.environ["PREFECT__CONTROL_PORT"] = str(port)
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-unknown-byte"

        control_listener.start()

        reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)
        writer.write(b"x")
        await writer.drain()

        data = await asyncio.wait_for(reader.read(1), timeout=2.0)
        assert data == b""
        assert control_listener.get_intent() is None

    def test_stop_closes_socket_and_allows_restart(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _FakeSocket:
            def __init__(self) -> None:
                self.connected_to: tuple[str, int] | None = None
                self.sent: list[bytes] = []
                self.shutdown_how: int | None = None
                self.closed = False
                self.recv_started = threading.Event()
                self.release_recv = threading.Event()

            def connect(self, address: tuple[str, int]) -> None:
                self.connected_to = address

            def sendall(self, data: bytes) -> None:
                self.sent.append(data)

            def recv(self, _size: int) -> bytes:
                self.recv_started.set()
                self.release_recv.wait(timeout=1.0)
                return b""

            def shutdown(self, how: int) -> None:
                self.shutdown_how = how
                self.release_recv.set()

            def close(self) -> None:
                self.closed = True
                self.release_recv.set()

        sockets = [_FakeSocket(), _FakeSocket()]

        monkeypatch.setattr(
            control_listener.socket,
            "socket",
            lambda *args, **kwargs: sockets.pop(0),
        )

        os.environ["PREFECT__CONTROL_PORT"] = "4201"
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-restart"
        control_listener.start()

        first = control_listener._socket
        assert first is not None
        assert first.recv_started.wait(timeout=1.0) is True
        assert first.connected_to == ("127.0.0.1", 4201)
        assert first.sent == [b"test-token-restart\n"]

        control_listener.stop()

        assert first.shutdown_how == control_listener.socket.SHUT_RDWR
        assert first.closed is True

        os.environ["PREFECT__CONTROL_PORT"] = "4202"
        os.environ["PREFECT__CONTROL_TOKEN"] = "test-token-restart-second"
        control_listener.start()

        second = control_listener._socket
        assert second is not None
        assert second.recv_started.wait(timeout=1.0) is True
        assert second.connected_to == ("127.0.0.1", 4202)
        assert second.sent == [b"test-token-restart-second\n"]

    def test_start_handles_connect_failure_gracefully(self) -> None:
        os.environ["PREFECT__CONTROL_PORT"] = "1"
        os.environ["PREFECT__CONTROL_TOKEN"] = "anything"
        control_listener.start()
        assert control_listener.get_intent() is None

    def test_stop_resets_bootstrap_config(self) -> None:
        os.environ["PREFECT__CONTROL_PORT"] = "4200"
        os.environ["PREFECT__CONTROL_TOKEN"] = "token"

        control_listener.configure_from_env()
        control_listener.stop()

        assert control_listener._configured is False
        assert control_listener._configured_port is None
        assert control_listener._configured_token is None

    def test_start_handles_invalid_port(self) -> None:
        os.environ["PREFECT__CONTROL_PORT"] = "not-a-number"
        os.environ["PREFECT__CONTROL_TOKEN"] = "anything"
        control_listener.start()
        assert control_listener.get_intent() is None
