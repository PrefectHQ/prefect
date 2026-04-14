"""Tests for the runner-side control channel.

These cover the channel in isolation: a real loopback listener with synthetic
clients standing in for the child process. End-to-end coverage (real
subprocesses) lives in `test_control_channel_e2e.py`.
"""

from __future__ import annotations

import asyncio
import socket
from uuid import uuid4

import pytest

from prefect.runner._control_channel import ControlChannel


@pytest.fixture
async def channel():
    async with ControlChannel(connect_timeout=1.0, ack_timeout=1.0) as ch:
        yield ch


async def _connect_client(port: int, token: str) -> socket.socket:
    """Connect to the channel like a real child process would.

    Returns a blocking socket the test can drive directly.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Use a generous connect timeout to avoid flakiness on busy CI.
    sock.settimeout(2.0)
    await asyncio.get_event_loop().run_in_executor(
        None, sock.connect, ("127.0.0.1", port)
    )
    sock.sendall(token.encode("ascii") + b"\n")
    return sock


class TestControlChannel:
    async def test_listener_binds_a_port(self, channel: ControlChannel) -> None:
        assert channel.port > 0

    async def test_register_returns_distinct_tokens(
        self, channel: ControlChannel
    ) -> None:
        port_a, token_a = channel.register(uuid4())
        port_b, token_b = channel.register(uuid4())
        assert port_a == port_b == channel.port
        assert token_a != token_b
        assert len(token_a) >= 16

    async def test_register_replaces_prior_registration(
        self, channel: ControlChannel
    ) -> None:
        flow_run_id = uuid4()
        _, token_a = channel.register(flow_run_id)
        _, token_b = channel.register(flow_run_id)
        assert token_a != token_b
        # Old token should no longer route to anything
        assert channel._tokens_to_id.get(token_a) is None

    async def test_unregister_drops_state(self, channel: ControlChannel) -> None:
        flow_run_id = uuid4()
        _, token = channel.register(flow_run_id)
        channel.unregister(flow_run_id)
        assert flow_run_id not in channel._registrations
        assert token not in channel._tokens_to_id

    async def test_signal_unregistered_returns_false(
        self, channel: ControlChannel
    ) -> None:
        result = await channel.signal(uuid4(), "cancel")
        assert result is False

    async def test_signal_with_no_connection_times_out(
        self, channel: ControlChannel
    ) -> None:
        flow_run_id = uuid4()
        channel.register(flow_run_id)
        result = await channel.signal(flow_run_id, "cancel")
        assert result is False

    async def test_signal_uses_connect_timeout_separately_from_ack_timeout(
        self,
    ) -> None:
        async with ControlChannel(connect_timeout=0.2, ack_timeout=5.0) as channel:
            flow_run_id = uuid4()
            channel.register(flow_run_id)
            result = await channel.signal(flow_run_id, "cancel")
            assert result is False

    async def test_signal_waits_past_connect_timeout_for_startup_deferred_ack(
        self,
    ) -> None:
        async with ControlChannel(
            connect_timeout=0.05,
            ack_timeout=0.01,
            startup_ack_timeout=0.25,
        ) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.02)

            async def delayed_ack_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                # Simulate a child that is connected but still loading flow
                # code before `capture_sigterm()` arms the synthetic-signal
                # bridge. This delay is longer than connect_timeout but
                # shorter than startup_ack_timeout.
                await asyncio.sleep(0.12)
                await loop.run_in_executor(None, sock.sendall, b"a")

            child_task = asyncio.create_task(delayed_ack_child())
            result = await channel.signal(flow_run_id, "cancel")
            await child_task
            sock.close()
            assert result is True

    async def test_signal_timeout_disconnects_child_so_late_ack_cannot_commit(
        self,
    ) -> None:
        async with ControlChannel(
            connect_timeout=0.05,
            ack_timeout=0.01,
            startup_ack_timeout=0.05,
        ) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.02)

            async def delayed_ack_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                await asyncio.sleep(0.1)
                try:
                    await loop.run_in_executor(None, sock.sendall, b"a")
                except OSError:
                    pass
                finally:
                    sock.close()

            child_task = asyncio.create_task(delayed_ack_child())
            result = await channel.signal(flow_run_id, "cancel")
            await child_task

            reg = channel._registrations[flow_run_id]
            assert result is False
            assert reg.disconnected.is_set()

    async def test_signal_returns_false_quickly_when_connected_child_disconnects_before_ack(
        self,
    ) -> None:
        async with ControlChannel(
            connect_timeout=0.3,
            ack_timeout=0.05,
            startup_ack_timeout=30.0,
        ) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.05)

            async def disconnecting_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                sock.close()

            child_task = asyncio.create_task(disconnecting_child())
            result = await asyncio.wait_for(channel.signal(flow_run_id, "cancel"), 0.5)
            await child_task

            assert result is False

    async def test_disconnect_clears_stale_ready_and_acked_state_for_repeat_signal(
        self,
    ) -> None:
        async with ControlChannel(
            connect_timeout=0.3,
            ack_timeout=0.05,
            startup_ack_timeout=0.3,
        ) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.05)
            sock.sendall(b"r")

            async def ack_then_disconnect() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                await loop.run_in_executor(None, sock.sendall, b"a")
                sock.close()

            child_task = asyncio.create_task(ack_then_disconnect())
            assert await channel.signal(flow_run_id, "cancel") is True
            await child_task

            reg = channel._registrations[flow_run_id]
            for _ in range(20):
                if reg.disconnected.is_set():
                    break
                await asyncio.sleep(0.01)

            assert reg.disconnected.is_set()
            assert not reg.connected.is_set()

            result = await asyncio.wait_for(channel.signal(flow_run_id, "cancel"), 0.2)
            assert result is False
            assert not reg.intent_acked.is_set()

    async def test_signal_returns_false_quickly_when_unregistered_while_waiting_to_connect(
        self,
    ) -> None:
        async with ControlChannel(
            connect_timeout=30.0,
            ack_timeout=0.05,
            startup_ack_timeout=30.0,
        ) as channel:
            flow_run_id = uuid4()
            channel.register(flow_run_id)

            signal_task = asyncio.create_task(channel.signal(flow_run_id, "cancel"))
            await asyncio.sleep(0.1)
            channel.unregister(flow_run_id)

            result = await asyncio.wait_for(signal_task, 0.5)
            assert result is False

    async def test_signal_uses_short_ack_timeout_after_ready_byte(
        self,
    ) -> None:
        async with ControlChannel(connect_timeout=0.3, ack_timeout=0.05) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.05)
            sock.sendall(b"r")
            for _ in range(20):
                if channel._registrations[flow_run_id].signal_handler_ready.is_set():
                    break
                await asyncio.sleep(0.01)
            assert channel._registrations[flow_run_id].signal_handler_ready.is_set()

            async def wedged_ready_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                # Never send the final ack; a ready-but-wedged child should
                # fall back on the short steady-state timeout.
                await asyncio.sleep(0.2)

            child_task = asyncio.create_task(wedged_ready_child())
            result = await asyncio.wait_for(channel.signal(flow_run_id, "cancel"), 0.2)
            await child_task
            sock.close()
            assert result is False

    async def test_not_ready_byte_clears_ready_state_and_restores_startup_budget(
        self,
    ) -> None:
        async with ControlChannel(connect_timeout=0.3, ack_timeout=0.05) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.05)
            sock.sendall(b"r")
            for _ in range(20):
                if channel._registrations[flow_run_id].signal_handler_ready.is_set():
                    break
                await asyncio.sleep(0.01)
            assert channel._registrations[flow_run_id].signal_handler_ready.is_set()

            sock.sendall(b"n")
            for _ in range(20):
                if not channel._registrations[
                    flow_run_id
                ].signal_handler_ready.is_set():
                    break
                await asyncio.sleep(0.01)
            assert not channel._registrations[flow_run_id].signal_handler_ready.is_set()

            async def delayed_ack_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                await asyncio.sleep(0.15)
                await loop.run_in_executor(None, sock.sendall, b"a")

            child_task = asyncio.create_task(delayed_ack_child())
            result = await channel.signal(flow_run_id, "cancel")
            await child_task
            sock.close()
            assert result is True

    async def test_ready_revocation_during_signal_extends_ack_wait_budget(
        self,
    ) -> None:
        async with ControlChannel(
            connect_timeout=0.3,
            ack_timeout=0.05,
            startup_ack_timeout=0.25,
        ) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)

            await asyncio.sleep(0.05)
            sock.sendall(b"r")
            for _ in range(20):
                if channel._registrations[flow_run_id].signal_handler_ready.is_set():
                    break
                await asyncio.sleep(0.01)
            assert channel._registrations[flow_run_id].signal_handler_ready.is_set()

            async def temporarily_not_ready_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                await loop.run_in_executor(None, sock.sendall, b"n")
                await asyncio.sleep(0.12)
                await loop.run_in_executor(None, sock.sendall, b"r")
                await loop.run_in_executor(None, sock.sendall, b"a")

            child_task = asyncio.create_task(temporarily_not_ready_child())
            result = await channel.signal(flow_run_id, "cancel")
            await child_task
            sock.close()
            assert result is True

    async def test_full_handshake_after_connection(
        self, channel: ControlChannel
    ) -> None:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        sock = await _connect_client(port, token)

        # Give the server task a moment to register the connection.
        await asyncio.sleep(0.05)

        async def fake_child() -> None:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, sock.recv, 1)
            assert data == b"c"
            await loop.run_in_executor(None, sock.sendall, b"a")

        child_task = asyncio.create_task(fake_child())
        result = await channel.signal(flow_run_id, "cancel")
        await child_task
        sock.close()
        assert result is True

    async def test_intent_queued_before_connection_is_delivered(
        self, channel: ControlChannel
    ) -> None:
        """If `signal()` is called before the child connects, the byte
        should be delivered as soon as the child does connect."""
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)

        # Connect 100ms after signal starts.
        async def delayed_client() -> None:
            await asyncio.sleep(0.1)
            sock = await _connect_client(port, token)
            loop = asyncio.get_event_loop()
            try:
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                await loop.run_in_executor(None, sock.sendall, b"a")
            finally:
                sock.close()

        client_task = asyncio.create_task(delayed_client())
        result = await channel.signal(flow_run_id, "cancel")
        await client_task
        assert result is True

    async def test_timeout_clears_pending_intent_before_late_connection(
        self,
    ) -> None:
        async with ControlChannel(connect_timeout=0.05, ack_timeout=0.05) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)

            result = await channel.signal(flow_run_id, "cancel")
            assert result is False
            assert channel._registrations[flow_run_id].pending_intent is None

            sock = await _connect_client(port, token)
            sock.settimeout(0.1)
            try:
                with pytest.raises(socket.timeout):
                    await asyncio.get_event_loop().run_in_executor(None, sock.recv, 1)
            finally:
                sock.close()

    async def test_invalid_token_is_rejected(self, channel: ControlChannel) -> None:
        flow_run_id = uuid4()
        port, _real_token = channel.register(flow_run_id)
        sock = await _connect_client(port, "deadbeef" * 4)

        # The server closes the connection on bad token; the client should
        # not be able to receive anything meaningful and signal should still
        # time out.
        await asyncio.sleep(0.05)
        result = await channel.signal(flow_run_id, "cancel")
        sock.close()
        assert result is False

    async def test_disabled_channel_raises_on_register(self) -> None:
        ch = ControlChannel()
        with pytest.raises(RuntimeError):
            ch.register(uuid4())

    async def test_disabled_channel_raises_on_port(self) -> None:
        ch = ControlChannel()
        with pytest.raises(RuntimeError):
            _ = ch.port

    async def test_bind_failure_degrades_to_disabled_channel(self, monkeypatch) -> None:
        async def _raise(*args, **kwargs):
            raise PermissionError("loopback bind denied")

        monkeypatch.setattr("asyncio.start_server", _raise)

        async with ControlChannel() as channel:
            result = await channel.signal(uuid4(), "cancel")

        assert result is False
        with pytest.raises(RuntimeError):
            channel.register(uuid4())
