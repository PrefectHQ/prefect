"""End-to-end test that spawns a real subprocess and exercises the full
loopback-channel cancel-intent path.

The runner-side `ControlChannel` lives in the test process. The child
is a real `subprocess.Popen` running a small Python program that:

1. Connects to the channel via `control_listener.start()`.
2. Installs Prefect's real SIGTERM bridge via `capture_sigterm()`.
3. Spins, waiting for SIGTERM.
4. Exits with a status code that tells the test which path was taken.

This is the highest-fidelity test for the intent-byte → termination trigger
→ `TerminationSignal` chain. Other tests cover the components in isolation;
this test guarantees they connect across a process boundary on the host's
actual Python.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import textwrap
from uuid import uuid4

import pytest

from prefect.runner._control_channel import ControlChannel

CHILD_PROGRAM = textwrap.dedent(
    """
    import os
    import sys
    import time

    from prefect._internal import control_listener
    from prefect.exceptions import TerminationSignal
    from prefect.utilities.engine import capture_sigterm

    control_listener.start()

    try:
        with capture_sigterm():
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                time.sleep(0.05)
    except TerminationSignal:
        if control_listener.get_intent() == "cancel":
            sys.exit(7)
        sys.exit(8)

    sys.exit(9)
    """
)


@pytest.mark.timeout(60)
async def test_cancel_intent_reaches_real_subprocess() -> None:
    async with ControlChannel(ack_timeout=5.0) as channel:
        flow_run_id = uuid4()
        port, token = channel.register(flow_run_id)

        env = {
            **dict(__import__("os").environ),
            "PREFECT__CONTROL_PORT": str(port),
            "PREFECT__CONTROL_TOKEN": token,
        }

        proc = subprocess.Popen(
            [sys.executable, "-c", CHILD_PROGRAM],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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

            acked = await channel.signal(flow_run_id, "cancel")
            assert acked, "child failed to ack cancel intent over loopback"

            if os.name != "nt":
                proc.send_signal(signal.SIGTERM)

            # Wait for the child to exit. The handler exits 7 on cancel intent.
            for _ in range(100):
                if proc.poll() is not None:
                    break
                await asyncio.sleep(0.05)

            assert proc.returncode is not None, "child did not exit in time"
            stdout, stderr = proc.communicate(timeout=5)
            assert proc.returncode == 7, (
                f"expected exit code 7 (cancel intent visible), got "
                f"{proc.returncode}; stderr: {stderr.decode(errors='replace')}"
            )
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)
            channel.unregister(flow_run_id)
