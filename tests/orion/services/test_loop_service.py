import asyncio
import signal
import sys

import pendulum
import pytest

from prefect.orion.services.loop_service import LoopService
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
            self.counter += 1
            if self.counter == 3:
                self.should_stop = True

    # run the service
    service = Service()
    await service.start()
    assert service.counter == 3

    # services reset their `should_stop` when they exit gracefully
    assert service.should_stop is False


async def test_loop_service_loops_kwarg():
    class Service(LoopService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            self.counter += 1

    # run the service
    service = Service()
    await service.start(loops=3)
    assert service.counter == 3

    # services reset their `should_stop` when they exit gracefully
    assert service.should_stop is False


async def test_loop_service_startup_shutdown():
    class Service(LoopService):
        state = []
        loop_seconds = 0

        async def setup(self):
            self.state.append("setup")
            await super().setup()

        async def run_once(self):
            pass

        async def shutdown(self):
            self.state.append("shutdown")
            await super().shutdown()

    service = Service()
    await service.start(loops=3)
    assert service.state == ["setup", "shutdown"]


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

    dt = pendulum.now("UTC")
    await service.stop()
    dt2 = pendulum.now("UTC")

    assert service.should_stop is False
    assert dt2 - dt < pendulum.duration(seconds=1)


@pytest.mark.skipif(
    sys.version_info < (3, 8), reason="signal.raise_signal requires Python >= 3.8"
)
class TestSignalHandling:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    async def test_handle_signals_to_shutdown(self, sig):
        service = LoopService()
        assert service.should_stop is False
        signal.raise_signal(sig)
        # yield so the signal handler can run
        await asyncio.sleep(0.1)
        assert service.should_stop is True

    async def test_handle_signals_can_be_disabled(self):
        service = LoopService(handle_signals=False)
        assert service.should_stop is False
        signal.raise_signal(signal.SIGTERM)
        # yield so the signal handler would have time to run
        await asyncio.sleep(0.1)
        assert service.should_stop is False
