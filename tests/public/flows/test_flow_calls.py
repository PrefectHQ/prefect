import asyncio

import anyio

import prefect


@prefect.flow
def identity_flow(x):
    return x


@prefect.flow
async def aidentity_flow(x):
    return x


def test_async_flow_called_with_asyncio():
    coro = aidentity_flow(1)
    assert asyncio.iscoroutine(coro)
    assert asyncio.run(coro) == 1


def test_async_flow_called_with_anyio():
    assert anyio.run(aidentity_flow, 1) == 1


async def test_async_flow_called_with_running_loop():
    coro = aidentity_flow(1)
    assert asyncio.iscoroutine(coro)
    assert await coro == 1


def test_sync_flow_called():
    assert identity_flow(1) == 1


async def test_sync_flow_called_with_running_loop():
    assert identity_flow(1) == 1
