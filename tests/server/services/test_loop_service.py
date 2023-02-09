import asyncio
import signal
import sys

import pendulum
import pytest

from prefect.server.services.loop_service import LoopService
from prefect.testing.utilities import flaky_on_windows


async def test_asyncio_sleep_accepts_negative_numbers():
    """Just in case a loop service computes a negative interval,
    this test ensures that the current behavior of asyncio accepting
    negative intervals remains valid."""
    await asyncio.sleep(-10.5)


async def test_loop_service_seconds_can_be_set_at_init():
    l1 = LoopService()
    l2 = LoopService(loop_seconds=100)
    assert l1.loop_seconds == 60
    assert l2.loop_seconds == 100


async def test_service_name_from_class():
    class MyService(LoopService):
        pass

    assert MyService().name == "MyService"


async def test_loop_service_run_once():
    class Service(LoopService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            assert self._should_stop is False
            assert self._is_running is True
            self.counter += 1
            if self.counter == 3:
                await self.stop(block=False)

    # run the service
    service = Service()
    await service.start()
    assert service.counter == 3

    assert service._is_running is False


async def test_loop_service_loops_kwarg():
    class Service(LoopService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            assert self._should_stop is False
            assert self._is_running is True
            self.counter += 1

    # run the service
    service = Service()
    await service.start(loops=3)
    assert service.counter == 3

    assert service._is_running is False


async def test_loop_service_run_multiple_times():
    class Service(LoopService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            self.counter += 1

    # run the service
    service = Service()
    await service.start(loops=3)
    await service.start(loops=2)
    await service.start(loops=1)
    assert service.counter == 6


async def test_loop_service_calls_on_start_on_stop_once():
    class Service(LoopService):
        state = []
        loop_seconds = 0

        async def _on_start(self):
            self.state.append("_on_start")
            await super()._on_start()

        async def run_once(self):
            pass

        async def _on_stop(self):
            self.state.append("_on_stop")
            await super()._on_stop()

    service = Service()
    await service.start(loops=3)
    assert service.state == ["_on_start", "_on_stop"]


@flaky_on_windows
async def test_early_stop():
    """Test that stop criterion is evaluated without waiting for loop_seconds"""

    class Service(LoopService):
        def __init__(self, loop_seconds: float = 1000):
            super().__init__(loop_seconds)

        async def run_once(self):
            pass

    service = Service()
    asyncio.create_task(service.start())
    # yield to let the service start
    await asyncio.sleep(0.1)
    assert service._is_running is True
    assert service._should_stop is False

    dt = pendulum.now("UTC")
    await service.stop()
    dt2 = pendulum.now("UTC")

    assert service._should_stop is True
    assert service._is_running is False
    assert dt2 - dt < pendulum.duration(seconds=1)


@flaky_on_windows
async def test_stop_block_escapes_deadlock(caplog):
    """Test that calling a blocking stop inside the service eventually returns"""

    class Service(LoopService):
        def __init__(self, loop_seconds: float = 0.1):
            super().__init__(loop_seconds)

        async def run_once(self):
            # calling a blocking stop inside run_once should create a deadlock
            await self.stop(block=True)

    service = Service()
    asyncio.create_task(service.start())

    # sleep for longer than one loop interval
    await asyncio.sleep(0.2)

    assert service._is_running is False
    assert "`stop(block=True)` was called on Service but" in caplog.text


@pytest.mark.skipif(
    sys.version_info < (3, 8), reason="signal.raise_signal requires Python >= 3.8"
)
class TestSignalHandling:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    async def test_handle_signals_to_shutdown(self, sig):
        service = LoopService()
        assert service._should_stop is False
        signal.raise_signal(sig)
        # yield so the signal handler can run
        await asyncio.sleep(0.1)
        assert service._should_stop is True

    async def test_handle_signals_can_be_disabled(self):
        service = LoopService(handle_signals=False)
        assert service._should_stop is False
        signal.raise_signal(signal.SIGTERM)
        # yield so the signal handler would have time to run
        await asyncio.sleep(0.1)
        assert service._should_stop is False
