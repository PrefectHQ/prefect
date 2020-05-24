# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import asyncio

import pytest

import prefect
from prefect_server.utilities.context import get_context, set_context


def test_set_and_get_context():
    ctx = get_context()
    assert "x" not in ctx

    with set_context(x=1):
        assert get_context()["x"] == 1

        with set_context(x=2):
            assert get_context()["x"] == 2

        assert get_context()["x"] == 1

    assert "x" not in ctx


class TestAsyncLeaks:

    """
    Context objects should not leak across asynchronous frames. To test this, we run
    two functions that are designed to set and unset the context in a staggered fashion. If
    the context leaks, then they will affect each other's context.
    """

    # assert context stays in frame
    async def test_server_context_doesnt_leak_across_async_frames(self):
        async def f(x):
            await asyncio.sleep(0.1)
            with set_context(x=x):
                assert x == get_context()["x"]
                await asyncio.sleep(0.2)
                assert x == get_context()["x"]

        futures = await asyncio.wait([f(1), f(2)])
        # there should be no errors because context was preserved across asyncio frames
        assert not any(f.exception() for f in futures[0])

    async def test_prefect_context_does_leak_across_async_frames(self):
        async def f(x):
            await asyncio.sleep(0.1)
            with prefect.context(x=x):
                assert x == prefect.context["x"]
                await asyncio.sleep(0.2)
                assert x == prefect.context["x"]

        futures = await asyncio.wait([f(1), f(2)])
        # the prefect context leaks across frames, so we expect errors
        assert any(f.exception() for f in futures[0])
