import asyncio

from prefect.orion.services.loop_service import LoopService


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
