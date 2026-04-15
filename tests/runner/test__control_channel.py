"""Tests for the runner-side control channel."""

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
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
        assert await channel.signal(uuid4(), "cancel") is False

    async def test_signal_with_no_connection_times_out(
        self, channel: ControlChannel
    ) -> None:
        flow_run_id = uuid4()
        channel.register(flow_run_id)
        assert await channel.signal(flow_run_id, "cancel") is False

    async def test_signal_does_not_wait_for_not_yet_connected_child(
        self,
    ) -> None:
        async with ControlChannel(connect_timeout=0.2, ack_timeout=5.0) as channel:
            flow_run_id = uuid4()
            channel.register(flow_run_id)
            result = await asyncio.wait_for(channel.signal(flow_run_id, "cancel"), 0.1)
            assert result is False

    async def test_signal_returns_false_quickly_when_connected_child_disconnects_before_ack(
        self,
    ) -> None:
        async with ControlChannel(connect_timeout=0.3, ack_timeout=0.05) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)
            for _ in range(20):
                if channel._registrations[flow_run_id].connected.is_set():
                    break
                await asyncio.sleep(0.01)
            assert channel._registrations[flow_run_id].connected.is_set()

            async def disconnecting_child() -> None:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, sock.recv, 1)
                assert data == b"c"
                sock.close()

            child_task = asyncio.create_task(disconnecting_child())
            result = await asyncio.wait_for(channel.signal(flow_run_id, "cancel"), 0.5)
            await child_task

            assert result is False

    async def test_disconnect_clears_stale_acked_state_for_repeat_signal(self) -> None:
        async with ControlChannel(connect_timeout=0.3, ack_timeout=0.05) as channel:
            flow_run_id = uuid4()
            port, token = channel.register(flow_run_id)
            sock = await _connect_client(port, token)
            for _ in range(20):
                if channel._registrations[flow_run_id].connected.is_set():
                    break
                await asyncio.sleep(0.01)
            assert channel._registrations[flow_run_id].connected.is_set()

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

    async def test_full_handshake_after_connection(
        self, channel: ControlChannel
    ) -> None:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)
        sock = await _connect_client(port, token)
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

    async def test_late_connection_after_fallback_receives_no_intent(
        self, channel: ControlChannel
    ) -> None:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)

        assert await channel.signal(flow_run_id, "cancel") is False

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
