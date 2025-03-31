import asyncio
import signal
from datetime import datetime, timedelta, timezone

import pytest

from prefect.server.services.base import LoopService
from prefect.settings.models.server.services import ServicesBaseSetting


async def test_asyncio_sleep_accepts_negative_numbers():
    """Just in case a loop service computes a negative interval,
    this test ensures that the current behavior of asyncio accepting
    negative intervals remains valid."""
    await asyncio.sleep(-10.5)


class ExampleService(LoopService):
    def service_settings(cls) -> ServicesBaseSetting:
        return ServicesBaseSetting(enabled=True)

    async def run_once(self) -> None:
        pass


async def test_loop_service_seconds_can_be_set_at_init():
    l1 = ExampleService()
    assert l1.loop_seconds == 60

    l2 = ExampleService(loop_seconds=100)
    assert l2.loop_seconds == 100


async def test_service_name_from_class():
    assert ExampleService().name == "ExampleService"


async def test_loop_service_run_once():
    class MyService(ExampleService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            assert self._should_stop is False
            assert self._is_running is True
            self.counter += 1
            if self.counter == 3:
                await self.stop(block=False)

    # run the service
    service = MyService()
    await service.start()
    assert service.counter == 3

    assert service._is_running is False


async def test_loop_service_loops_kwarg():
    class MyService(ExampleService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            assert self._should_stop is False
            assert self._is_running is True
            self.counter += 1

    # run the service
    service = MyService()
    await service.start(loops=3)
    assert service.counter == 3

    assert service._is_running is False


async def test_loop_service_run_multiple_times():
    class MyService(ExampleService):
        loop_seconds = 0
        counter = 0

        async def run_once(self):
            self.counter += 1

    # run the service
    service = MyService()
    await service.start(loops=3)
    await service.start(loops=2)
    await service.start(loops=1)
    assert service.counter == 6


async def test_loop_service_calls_on_start_on_stop_once():
    class MyService(ExampleService):
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

    service = MyService()
    await service.start(loops=3)
    assert service.state == ["_on_start", "_on_stop"]


async def test_early_stop():
    """Test that stop criterion is evaluated without waiting for loop_seconds"""

    LOOP_INTERVAL = 120

    service = ExampleService(loop_seconds=LOOP_INTERVAL)
    asyncio.create_task(service.start())
    # yield to let the service start
    await asyncio.sleep(0.1)
    assert service._is_running is True
    assert service._should_stop is False

    dt = datetime.now(timezone.utc)
    await service.stop()
    dt2 = datetime.now(timezone.utc)

    assert service._should_stop is True
    assert service._is_running is False
    assert dt2 - dt < timedelta(seconds=LOOP_INTERVAL)


async def test_stop_block_escapes_deadlock(caplog):
    """Test that calling a blocking stop inside the service eventually returns"""

    LOOP_INTERVAL = 0.1

    class MyService(ExampleService):
        loop_seconds = LOOP_INTERVAL

        async def run_once(self):
            # calling a blocking stop inside run_once should create a deadlock
            await self.stop(block=True)

    service = MyService()
    asyncio.create_task(service.start())

    # sleep for longer than one loop interval
    await asyncio.sleep(LOOP_INTERVAL * 5)

    assert service._is_running is False
    assert "`stop(block=True)` was called on MyService but" in caplog.text


class TestSignalHandling:
    @pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
    async def test_can_handle_signals_to_shutdown(self, sig):
        class MyService(ExampleService):
            pass

        service = MyService(handle_signals=True)
        assert service._should_stop is False
        signal.raise_signal(sig)
        # yield so the signal handler can run
        await asyncio.sleep(0.1)
        assert service._should_stop is True

    async def test_does_not_handle_signals_by_default(self):
        class MyService(ExampleService):
            pass

        service = MyService()
        assert service._should_stop is False
        signal.raise_signal(signal.SIGTERM)
        # yield so the signal handler would have time to run
        await asyncio.sleep(0.1)
        assert service._should_stop is False
