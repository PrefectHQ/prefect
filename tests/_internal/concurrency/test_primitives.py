import anyio

from prefect._internal.concurrency.primitives import Event


def test_event_set_in_sync_context_before_wait():
    event = Event()
    event.set()

    async def main():
        with anyio.fail_after(1):
            await event.wait()

    anyio.run(main)


async def test_event_created_and_set_from_sync_thread():
    def create_event():
        return Event()

    async def create_and_set_event(task_status):
        event = await anyio.to_thread.run_sync(create_event)
        task_status.started(event)
        await anyio.to_thread.run_sync(event.set)

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            event = await tg.start(create_and_set_event)
            tg.start_soon(event.wait)


async def test_event_set_in_async_context_before_wait():
    event = Event()
    event.set()
    await event.wait()


async def test_event_set_from_async_task():
    event = Event()

    async def set_event():
        event.set()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(event.wait)
            tg.start_soon(set_event)


async def test_event_set_from_sync_thread():
    event = Event()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(event.wait)
            tg.start_soon(anyio.to_thread.run_sync, event.set)


async def test_event_many_set_and_wait():
    event = Event()
    with anyio.fail_after(5):
        async with anyio.create_task_group() as tg:
            for _ in range(100):
                # Interleave many set and wait operations
                tg.start_soon(event.wait)
                tg.start_soon(anyio.to_thread.run_sync, event.set)


async def test_event_set_from_sync_thread_before_wait():
    event = Event()

    async def set_event(task_status):
        await anyio.to_thread.run_sync(event.set)
        task_status.started()

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            await tg.start(set_event)
            tg.start_soon(event.wait)


async def test_event_set_from_async_thread():
    event = Event()

    async def set_event():
        event.set()

    def set_event_in_new_loop():
        anyio.run(set_event)

    with anyio.fail_after(1):
        async with anyio.create_task_group() as tg:
            tg.start_soon(event.wait)
            tg.start_soon(anyio.to_thread.run_sync, set_event_in_new_loop)


async def test_event_set_from_async_thread_before_wait():
    event = Event()

    async def set_event():
        event.set()

    def set_event_in_new_loop():
        anyio.run(set_event)

    await anyio.to_thread.run_sync(set_event_in_new_loop)
    with anyio.fail_after(1):
        await event.wait()


async def test_dependent_events_in_two_loops_do_not_deadlock():
    event_one = None
    event_two = None

    async def one():
        nonlocal event_one
        event_one = Event()
        while event_two is None:
            await anyio.sleep(0)
        event_two.set()
        await event_one.wait()

    async def two():
        nonlocal event_two
        event_two = Event()
        while event_one is None:
            await anyio.sleep(0)
        event_one.set()
        await event_two.wait()

    with anyio.fail_after(5):
        async with anyio.create_task_group() as tg:
            tg.start_soon(anyio.to_thread.run_sync, anyio.run, one)
            tg.start_soon(anyio.to_thread.run_sync, anyio.run, two)


async def test_event_wait_in_different_loop():
    event = Event()

    async def wait_for_event():
        await event.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(anyio.to_thread.run_sync, anyio.run, wait_for_event)
        event.set()


async def test_event_wait_in_multiple_loops():
    event = Event()

    async def wait_for_event():
        await event.wait()

    async with anyio.create_task_group() as tg:
        tg.start_soon(anyio.to_thread.run_sync, anyio.run, wait_for_event)
        tg.start_soon(anyio.to_thread.run_sync, anyio.run, wait_for_event)
        tg.start_soon(anyio.to_thread.run_sync, anyio.run, wait_for_event)
        event.set()


async def test_event_is_set():
    event = Event()
    assert not event.is_set()
    event.set()
    assert event.is_set()
