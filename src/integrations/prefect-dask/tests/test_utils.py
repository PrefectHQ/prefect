import sys

import dask
import pytest
from distributed import Client
from prefect_dask import DaskTaskRunner, get_async_dask_client, get_dask_client

from prefect import flow, task


class TestDaskSyncClient:
    def test_from_task(self):
        @task
        def test_task():
            delayed_num = dask.delayed(42)
            with get_dask_client() as client:
                assert isinstance(client, Client)
                result = client.compute(delayed_num).result()
            return result

        @flow(task_runner=DaskTaskRunner)
        def test_flow():
            future = test_task.submit()
            return future.result()

        assert test_flow() == 42

    def test_from_flow(self):
        @flow(task_runner=DaskTaskRunner)
        def test_flow():
            delayed_num = dask.delayed(42)
            with get_dask_client() as client:
                assert isinstance(client, Client)
                result = client.compute(delayed_num).result()
            return result

        assert test_flow() == 42

    def test_outside_run_context(self):
        delayed_num = dask.delayed(42)
        with get_dask_client() as client:
            assert isinstance(client, Client)
            result = client.compute(delayed_num).result()
        assert result == 42

    @pytest.mark.parametrize("timeout", [None, 8])
    def test_include_timeout(self, timeout):
        delayed_num = dask.delayed(42)
        with get_dask_client(timeout=timeout) as client:
            assert isinstance(client, Client)
            if timeout is not None:
                assert client._timeout == timeout
            result = client.compute(delayed_num).result()
        assert result == 42


class TestDaskAsyncClient:
    async def test_from_task(self):
        @task
        async def test_task():
            delayed_num = dask.delayed(42)
            async with get_async_dask_client() as client:
                assert isinstance(client, Client)
                result = await client.compute(delayed_num).result()
            return result

        @flow(task_runner=DaskTaskRunner)
        async def test_flow():
            future = await test_task.submit()
            return await future.result()

        assert (await test_flow()) == 42

    def test_from_sync_task_error(self):
        @task
        def test_task():
            with get_async_dask_client():
                pass

        @flow(task_runner=DaskTaskRunner)
        def test_flow():
            test_task.submit()

        if sys.version_info < (3, 11):
            with pytest.raises(AttributeError, match="__enter__"):
                test_flow()
        else:
            with pytest.raises(
                TypeError, match="not support the context manager protocol"
            ):
                test_flow()

    async def test_from_flow(self):
        @flow(task_runner=DaskTaskRunner)
        async def test_flow():
            delayed_num = dask.delayed(42)
            async with get_async_dask_client() as client:
                assert isinstance(client, Client)
                result = await client.compute(delayed_num).result()
            return result

        assert (await test_flow()) == 42

    def test_from_sync_flow_error(self):
        @flow(task_runner=DaskTaskRunner)
        def test_flow():
            with get_async_dask_client():
                pass

        if sys.version_info < (3, 11):
            with pytest.raises(AttributeError, match="__enter__"):
                test_flow()
        else:
            with pytest.raises(
                TypeError, match="not support the context manager protocol"
            ):
                test_flow()

    async def test_outside_run_context(self):
        delayed_num = dask.delayed(42)
        async with get_async_dask_client() as client:
            assert isinstance(client, Client)
            result = await client.compute(delayed_num).result()
        assert result == 42

    @pytest.mark.parametrize("timeout", [None, 8])
    async def test_include_timeout(self, timeout):
        delayed_num = dask.delayed(42)
        async with get_async_dask_client(timeout=timeout) as client:
            assert isinstance(client, Client)
            if timeout is not None:
                assert client._timeout == timeout
            result = await client.compute(delayed_num).result()
        assert result == 42
