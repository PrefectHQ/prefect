"""Tests for the child-side runner control listener.

These exercise the listener with a real loopback socket on the other end so
we cover the actual byte exchange and `_thread.interrupt_main` path. The
fake "runner" here is just an `asyncio.start_server` we drive directly.
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
            control_listener.start()

            reader, writer = await asyncio.wait_for(accepted.get(), timeout=2.0)

            # Send the cancel byte and wait for the ack.
            writer.write(b"c")
            await writer.drain()
            ack = await asyncio.wait_for(reader.read(1), timeout=2.0)
            assert ack == b"a"

            # Intent flag should be set.
            assert control_listener.get_intent() == "cancel"

            # interrupt_main should have triggered our handler. Give it a
            # moment to be processed at the next bytecode boundary.
            for _ in range(50):
                if signal_received.is_set():
                    break
                time.sleep(0.01)
            assert signal_received.is_set()
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
