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
    async with ControlChannel(ack_timeout=1.0) as ch:
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
