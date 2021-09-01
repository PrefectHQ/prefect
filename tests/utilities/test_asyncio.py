import pytest


from prefect.utilities.asyncio import (
    run_async_in_new_loop,
    run_sync_in_worker_thread,
    run_async_from_worker_thread,
    sync_compatible,
    in_async_worker_thread,
    in_async_main_thread,
)


def test_in_async_main_thread_sync():
    assert not in_async_main_thread()


async def test_in_async_main_thread_async():
    assert in_async_main_thread()


async def test_in_async_main_thread_worker():
    assert not await run_sync_in_worker_thread(in_async_main_thread)


def test_in_async_worker_thread_sync():
    assert not in_async_worker_thread()


async def test_in_async_worker_thread_async():
    assert not in_async_worker_thread()


async def test_in_async_worker_thread_worker():
    assert await run_sync_in_worker_thread(in_async_worker_thread)


def test_run_async_in_new_loop():
    async def foo(x, y, z=3):
        return x + y + z

    assert run_async_in_new_loop(foo, 1, y=2) == 6


async def test_run_async_in_new_loop_does_not_work_from_async():
    async def foo(x, y, z=3):
        return x + y + z

    with pytest.raises(RuntimeError, match="Already running"):
        run_async_in_new_loop(foo, 1, y=2)


async def test_run_sync_in_worker_thread():
    def foo(x, y, z=3):
        return x + y + z

    assert await run_sync_in_worker_thread(foo, 1, y=2) == 6


async def test_run_async_from_worker_thread():
    async def foo(x, y, z=3):
        return x + y + z

    def outer():
        return run_async_from_worker_thread(foo, 1, y=2)

    assert await run_sync_in_worker_thread(outer) == 6


@sync_compatible
async def sync_compatible_fn(x, y, z=3):
    return x + y + z


class SyncCompatibleClass:
    attr = 4

    @staticmethod
    @sync_compatible
    async def static_method(x, y, z=3):
        assert SyncCompatibleClass.attr == 4, "Can access class attributes"
        return x + y + z

    @classmethod
    @sync_compatible
    async def class_method(cls, x, y, z=3):
        assert cls.attr == 4, "`cls` is sent correctly`"
        return x + y + z

    @sync_compatible
    async def instance_method(self, x, y, z=3):
        assert self.attr == 4, "`self` is sent correctly"
        return x + y + z


SYNC_COMPAT_TEST_CASES = [
    sync_compatible_fn,
    SyncCompatibleClass.static_method,
    SyncCompatibleClass.class_method,
    SyncCompatibleClass().instance_method,
]


@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
def test_sync_compatible_call_from_sync(fn):
    assert fn(1, y=2) == 6


@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
async def test_sync_compatible_call_from_async(fn):
    assert await fn(1, y=2) == 6


@pytest.mark.parametrize("fn", SYNC_COMPAT_TEST_CASES)
async def test_sync_compatible_call_from_worker(fn):
    def run_fn():
        return fn(1, y=2)

    assert await run_sync_in_worker_thread(run_fn) == 6


def test_sync_compatible_allows_direct_access_to_async_fn():
    async def foo():
        pass

    assert sync_compatible(foo).aio is foo


def test_sync_compatible_requires_async_function():
    with pytest.raises(TypeError, match="must be async"):

        @sync_compatible
        def foo():
            pass
