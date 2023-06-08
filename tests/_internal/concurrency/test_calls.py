import asyncio
import time

import pytest

from prefect._internal.concurrency.calls import Call
from prefect._internal.concurrency.cancellation import CancelledError


def identity(x):
    return x


async def aidentity(x):
    return x


def raises(exc):
    raise exc


async def araises(exc):
    raise exc


@pytest.mark.parametrize("fn", [identity, aidentity])
def test_sync_call(fn):
    call = Call.new(fn, 1)
    assert call() == 1


async def test_async_call_sync_function():
    call = Call.new(identity, 1)
    assert call() == 1


async def test_async_call_async_function():
    call = Call.new(aidentity, 1)
    assert await call() == 1


@pytest.mark.parametrize("fn", [identity, aidentity])
def test_call_result(fn):
    call = Call.new(fn, 1)
    call.run()
    assert call.result() == 1


@pytest.mark.parametrize("fn", [raises, araises])
def test_call_result_exception(fn):
    call = Call.new(fn, ValueError("test"))
    call.run()
    with pytest.raises(ValueError, match="test"):
        call.result()


@pytest.mark.parametrize("fn", [raises, araises])
def test_call_result_base_exception(fn):
    call = Call.new(fn, BaseException("test"))
    call.run()
    with pytest.raises(BaseException, match="test"):
        call.result()


@pytest.mark.parametrize(
    "exception_cls", [BaseException, KeyboardInterrupt, SystemExit]
)
async def test_async_call_result_base_exception_with_event_loop(exception_cls):
    call = Call.new(araises, exception_cls("test"))
    await call.run()
    with pytest.raises(exception_cls, match="test"):
        call.result()


@pytest.mark.parametrize("fn", [time.sleep, asyncio.sleep], ids=["sync", "async"])
def test_call_timeout(fn):
    call = Call.new(fn, 2)
    call.set_timeout(1)
    call.run()
    with pytest.raises(CancelledError):
        call.result()
    assert call.cancelled()


def test_call_future_cancelled():
    call = Call.new(identity, 2)
    call.future.cancel()
    call.run()
    with pytest.raises(CancelledError):
        call.result()
    assert call.cancelled()
