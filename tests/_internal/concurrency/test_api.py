import contextlib
import contextvars

import pytest

from prefect._internal.concurrency.api import create_call, from_async, from_sync


def identity(x):
    return x


async def aidentity(x):
    return x


TEST_CONTEXTVAR = contextvars.ContextVar("TEST_CONTEXTVAR")


def get_contextvar():
    return TEST_CONTEXTVAR.get()


async def aget_contextvar():
    return TEST_CONTEXTVAR.get()


@contextlib.contextmanager
def set_contextvar(value):
    try:
        token = TEST_CONTEXTVAR.set(value)
        yield
    finally:
        TEST_CONTEXTVAR.reset(token)


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_call_soon_in_worker_thread(work):
    supervisor = from_async.supervise_call_in_worker_thread(create_call(work, 1))
    assert await supervisor.result() == 1


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_call_soon_in_worker_thread(work):
    supervisor = from_sync.supervise_call_in_worker_thread(create_call(work, 1))
    assert supervisor.result() == 1


async def test_from_async_supervise_call_in_runtime_thread():
    supervisor = from_async.supervise_call_in_runtime_thread(create_call(aidentity, 1))
    assert await supervisor.result() == 1


def test_from_sync_supervise_call_in_runtime_thread():
    supervisor = from_sync.supervise_call_in_runtime_thread(create_call(aidentity, 1))
    assert supervisor.result() == 1


async def test_from_async_supervise_call_in_runtime_thread_must_be_coroutine_fn():
    with pytest.raises(TypeError, match="coroutine"):
        from_async.supervise_call_in_runtime_thread(create_call(identity, 1))


def test_from_sync_supervise_call_in_runtime_thread_must_be_coroutine_fn():
    with pytest.raises(TypeError, match="coroutine"):
        from_sync.supervise_call_in_runtime_thread(create_call(identity, 1))


@pytest.mark.parametrize("from_module", [from_async, from_sync])
async def test_send_call_to_supervising_thread_no_supervisor(from_module):
    with pytest.raises(RuntimeError, match="No supervisor"):
        getattr(from_module, "send_call_to_supervising_thread")(
            create_call(identity, 1)
        )


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_send_call_to_supervising_thread_from_worker(work):
    async def worker():
        future = from_async.send_call_to_supervising_thread(create_call(work, 1))
        assert await future == 1
        return 2

    supervisor = from_async.supervise_call_in_worker_thread(create_call(worker))
    assert await supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_send_call_to_supervising_thread_from_worker(work):
    def worker():
        future = from_sync.send_call_to_supervising_thread(create_call(work, 1))
        assert future.result() == 1
        return 2

    supervisor = from_sync.supervise_call_in_worker_thread(create_call(worker))
    assert supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
async def test_from_async_send_call_to_supervising_thread_from_runtime(work):
    async def from_runtime():
        future = from_async.send_call_to_supervising_thread(create_call(work, 1))
        assert await future == 1
        return 2

    supervisor = from_async.supervise_call_in_runtime_thread(create_call(from_runtime))
    assert await supervisor.result() == 2


@pytest.mark.parametrize("work", [identity, aidentity])
def test_from_sync_send_call_to_supervising_thread_from_runtime(work):
    async def from_runtime():
        future = from_async.send_call_to_supervising_thread(create_call(work, 1))
        assert await future == 1
        return 2

    supervisor = from_sync.supervise_call_in_runtime_thread(create_call(from_runtime))
    assert supervisor.result() == 2


async def test_from_async_supervise_call_in_runtime_thread_captures_context_variables():
    with set_contextvar("test"):
        supervisor = from_async.supervise_call_in_runtime_thread(
            create_call(aget_contextvar)
        )
        assert await supervisor.result() == "test"


def test_from_sync_supervise_call_in_runtime_thread_captures_context_variables():
    with set_contextvar("test"):
        supervisor = from_sync.supervise_call_in_runtime_thread(
            create_call(aget_contextvar)
        )
        assert supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_call_soon_in_worker_thread_captures_context_variables(get):
    with set_contextvar("test"):
        supervisor = from_async.supervise_call_in_worker_thread(create_call(get))
        assert await supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_call_soon_in_worker_thread_captures_context_variables(get):
    with set_contextvar("test"):
        supervisor = from_sync.supervise_call_in_worker_thread(create_call(get))
        assert supervisor.result() == "test"


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
async def test_from_async_send_call_to_supervising_thread_captures_context_varaibles(
    get,
):
    async def from_runtime():
        with set_contextvar("test"):
            future = from_async.send_call_to_supervising_thread(create_call(get))
        assert await future == "test"

    supervisor = from_async.supervise_call_in_runtime_thread(create_call(from_runtime))
    await supervisor.result()


@pytest.mark.parametrize("get", [get_contextvar, aget_contextvar])
def test_from_sync_send_call_to_supervising_thread_captures_context_varaibles(get):
    async def from_runtime():
        with set_contextvar("test"):
            future = from_async.send_call_to_supervising_thread(create_call(get))
        assert await future == "test"

    supervisor = from_sync.supervise_call_in_runtime_thread(create_call(from_runtime))
    supervisor.result()
