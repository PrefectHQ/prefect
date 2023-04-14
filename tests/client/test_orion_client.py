import datetime
import os
import random
import threading
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Generator, List
from unittest.mock import ANY, MagicMock, Mock
from uuid import UUID, uuid4

import anyio
import httpcore
import httpx
import pendulum
import pydantic
import pytest
from fastapi import Depends, FastAPI, status
from fastapi.security import HTTPBearer

import prefect.client.schemas as client_schemas
import prefect.context
import prefect.exceptions
from prefect import flow, tags
from prefect.client.orchestration import PrefectClient, ServerType, get_client
from prefect.client.schemas import OrchestrationResult
from prefect.client.utilities import inject_client
from prefect.deprecated.data_documents import DataDocument
from prefect.server import schemas
from prefect.server.api.server import SERVER_API_VERSION, create_app
from prefect.server.schemas.actions import ArtifactCreate, LogCreate, WorkPoolCreate
from prefect.server.schemas.core import FlowRunNotificationPolicy
from prefect.server.schemas.filters import (
    FlowRunNotificationPolicyFilter,
    LogFilter,
    LogFilterFlowRunId,
)
from prefect.server.schemas.schedules import IntervalSchedule
from prefect.server.schemas.states import StateType
from prefect.settings import (
    PREFECT_API_DATABASE_MIGRATE_ON_START,
    PREFECT_API_KEY,
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    temporary_settings,
)
from prefect.states import Completed, Pending, Running, Scheduled, State
from prefect.tasks import task
from prefect.testing.utilities import AsyncMock, exceptions_equal


class TestGetClient:
    def test_get_client_returns_client(self):
        assert isinstance(get_client(), PrefectClient)

    def test_get_client_does_not_cache_client(self):
        assert get_client() is not get_client()

    def test_get_client_cache_uses_profile_settings(self):
        client = get_client()
        with temporary_settings(updates={PREFECT_API_KEY: "FOO"}):
            new_client = get_client()
            assert isinstance(new_client, PrefectClient)
            assert new_client is not client


class TestClientProxyAwareness:
    """Regression test for https://github.com/PrefectHQ/nebula/issues/2356, where
    a customer reported that the Cloud client supported proxies, but the Orion client
    did not.  This test suite is implementation-specific to httpx/httpcore, as there are
    no other inexpensive ways to confirm both the proxy-awareness and preserving the
    retry behavior without probing into the implementation details of the libraries."""

    @pytest.fixture()
    def remote_https_orion(self) -> Generator[httpx.URL, None, None]:
        orion_url = "https://127.0.0.1:4242/"
        with temporary_settings(updates={PREFECT_API_URL: orion_url}):
            yield httpx.URL(orion_url)

    def test_unproxied_remote_client_will_retry(self, remote_https_orion: httpx.URL):
        """The original issue here was that we were overriding the `transport` in
        order to set the retries to 3; this is what circumvented the proxy support.
        This test (and those below) should confirm that we are setting the retries on
        the transport's pool in all cases."""
        httpx_client = get_client()._client
        assert isinstance(httpx_client, httpx.AsyncClient)

        transport_for_orion = httpx_client._transport_for_url(remote_https_orion)
        assert isinstance(transport_for_orion, httpx.AsyncHTTPTransport)

        pool = transport_for_orion._pool
        assert isinstance(pool, httpcore.AsyncConnectionPool)
        assert pool._retries == 3  # set in prefect.client.orchestration.get_client()

    def test_users_can_still_provide_transport(self, remote_https_orion: httpx.URL):
        """If users want to supply an alternative transport, they still can and
        we will not alter it"""
        httpx_settings = {"transport": httpx.AsyncHTTPTransport(retries=11)}
        httpx_client = get_client(httpx_settings)._client
        assert isinstance(httpx_client, httpx.AsyncClient)

        transport_for_orion = httpx_client._transport_for_url(remote_https_orion)
        assert isinstance(transport_for_orion, httpx.AsyncHTTPTransport)

        pool = transport_for_orion._pool
        assert isinstance(pool, httpcore.AsyncConnectionPool)
        assert pool._retries == 11  # not overridden by get_client() in this case

    @pytest.fixture
    def https_proxy(self) -> Generator[httpcore.URL, None, None]:
        original = os.environ.get("HTTPS_PROXY")
        try:
            os.environ["HTTPS_PROXY"] = "https://127.0.0.1:6666"
            yield httpcore.URL(os.environ["HTTPS_PROXY"])
        finally:
            if original is None:
                del os.environ["HTTPS_PROXY"]
            else:
                os.environ["HTTPS_PROXY"] = original

    async def test_client_is_aware_of_https_proxy(
        self, remote_https_orion: httpx.URL, https_proxy: httpcore.URL
    ):
        httpx_client = get_client()._client
        assert isinstance(httpx_client, httpx.AsyncClient)

        transport_for_orion = httpx_client._transport_for_url(remote_https_orion)
        assert isinstance(transport_for_orion, httpx.AsyncHTTPTransport)

        pool = transport_for_orion._pool
        assert isinstance(pool, httpcore.AsyncHTTPProxy)
        assert pool._proxy_url == https_proxy
        assert pool._retries == 3  # set in prefect.client.orchestration.get_client()

    @pytest.fixture()
    def remote_http_orion(self) -> Generator[httpx.URL, None, None]:
        orion_url = "http://127.0.0.1:4242/"
        with temporary_settings(updates={PREFECT_API_URL: orion_url}):
            yield httpx.URL(orion_url)

    @pytest.fixture
    def http_proxy(self) -> Generator[httpcore.URL, None, None]:
        original = os.environ.get("HTTP_PROXY")
        try:
            os.environ["HTTP_PROXY"] = "http://127.0.0.1:6666"
            yield httpcore.URL(os.environ["HTTP_PROXY"])
        finally:
            if original is None:
                del os.environ["HTTP_PROXY"]
            else:
                os.environ["HTTP_PROXY"] = original

    async def test_client_is_aware_of_http_proxy(
        self, remote_http_orion: httpx.URL, http_proxy: httpcore.URL
    ):
        httpx_client = get_client()._client
        assert isinstance(httpx_client, httpx.AsyncClient)

        transport_for_orion = httpx_client._transport_for_url(remote_http_orion)
        assert isinstance(transport_for_orion, httpx.AsyncHTTPTransport)

        pool = transport_for_orion._pool
        assert isinstance(pool, httpcore.AsyncHTTPProxy)
        assert pool._proxy_url == http_proxy
        assert pool._retries == 3  # set in prefect.client.orchestration.get_client()


class TestInjectClient:
    @staticmethod
    @inject_client
    async def injected_func(client: PrefectClient):
        assert client._started, "Client should be started during function"
        assert not client._closed, "Client should be closed during function"
        # Client should be usable during function
        await client.api_healthcheck()
        return client

    async def test_get_new_client(self):
        client = await TestInjectClient.injected_func()
        assert isinstance(client, PrefectClient)
        assert client._closed, "Client should be closed after function returns"

    async def test_get_new_client_with_explicit_none(self):
        client = await TestInjectClient.injected_func(client=None)
        assert isinstance(client, PrefectClient)
        assert client._closed, "Client should be closed after function returns"

    async def test_use_existing_client(self, orion_client):
        client = await TestInjectClient.injected_func(client=orion_client)
        assert client is orion_client, "Client should be the same object"
        assert not client._closed, "Client should not be closed after function returns"

    async def test_does_not_use_existing_client_from_flow_run_ctx(self, orion_client):
        with prefect.context.FlowRunContext.construct(client=orion_client):
            client = await TestInjectClient.injected_func()
        assert client is not orion_client, "Client should not be the same object"
        assert client._closed, "Client should be closed after function returns"

    async def test_does_not_use_existing_client_from_task_run_ctx(self, orion_client):
        with prefect.context.FlowRunContext.construct(client=orion_client):
            client = await TestInjectClient.injected_func()
        assert client is not orion_client, "Client should not be the same object"
        assert client._closed, "Client should be closed after function returns"

    async def test_does_not_use_existing_client_from_flow_run_ctx_with_null_kwarg(
        self, orion_client
    ):
        with prefect.context.FlowRunContext.construct(client=orion_client):
            client = await TestInjectClient.injected_func(client=None)
        assert client is not orion_client, "Client should not be the same object"
        assert client._closed, "Client should be closed after function returns"


def not_enough_open_files() -> bool:
    """
    The current process does not currently allow enough open files for this test.
    You can increase the number of open files with `ulimit -n 512`.
    """
    try:
        import resource
    except ImportError:
        # resource limits is not a concept on all systems, notably Windows
        return False

    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    return soft_limit < 512 or hard_limit < 512


def make_lifespan(startup, shutdown) -> callable:
    async def lifespan(app):
        try:
            startup()
            yield
        finally:
            shutdown()

    return asynccontextmanager(lifespan)


class TestClientContextManager:
    async def test_client_context_cannot_be_reentered(self):
        client = PrefectClient("http://foo.test")
        async with client:
            with pytest.raises(RuntimeError, match="cannot be started more than once"):
                async with client:
                    pass

    async def test_client_context_cannot_be_reused(self):
        client = PrefectClient("http://foo.test")
        async with client:
            pass

        with pytest.raises(RuntimeError, match="cannot be started again after closing"):
            async with client:
                pass

    async def test_client_context_manages_app_lifespan(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        client = PrefectClient(app)
        startup.assert_not_called()
        shutdown.assert_not_called()

        async with client:
            startup.assert_called_once()
            shutdown.assert_not_called()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_calls_app_lifespan_once_despite_nesting(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        startup.assert_not_called()
        shutdown.assert_not_called()

        async with PrefectClient(app):
            async with PrefectClient(app):
                async with PrefectClient(app):
                    startup.assert_called_once()
            shutdown.assert_not_called()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_manages_app_lifespan_on_sequential_usage(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        async with PrefectClient(app):
            pass

        assert startup.call_count == 1
        assert shutdown.call_count == 1

        async with PrefectClient(app):
            assert startup.call_count == 2
            assert shutdown.call_count == 1

        assert startup.call_count == 2
        assert shutdown.call_count == 2

    async def test_client_context_lifespan_is_robust_to_async_concurrency(self):
        startup = MagicMock(side_effect=lambda: print("Startup called!"))
        shutdown = MagicMock(side_effect=lambda: print("Shutdown called!!"))

        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        one_started = anyio.Event()
        one_exited = anyio.Event()
        two_started = anyio.Event()

        async def one():
            async with PrefectClient(app):
                print("Started one")
                one_started.set()
                startup.assert_called_once()
                shutdown.assert_not_called()
                print("Waiting for two to start...")
                await two_started.wait()
                # Exit after two has started
                print("Exiting one...")
            one_exited.set()

        async def two():
            await one_started.wait()
            # Enter after one has started but before one has exited
            async with PrefectClient(app):
                print("Started two")
                two_started.set()
                # Give time for one to try to exit
                # If were to wait on the `one_exited` event, this test would timeout
                # as we'd create a deadlock where one refuses to exit until the clients
                # depending on its lifespan are done
                await anyio.sleep(1)
                startup.assert_called_once()
                shutdown.assert_not_called()
                print("Exiting two...")

        # Run concurrently
        with anyio.fail_after(5):  # Kill if a deadlock occurs
            async with anyio.create_task_group() as tg:
                tg.start_soon(one)
                tg.start_soon(two)

        startup.assert_called_once()
        shutdown.assert_called_once()

    @pytest.mark.skipif(not_enough_open_files(), reason=not_enough_open_files.__doc__)
    async def test_client_context_lifespan_is_robust_to_threaded_concurrency(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        async def enter_client(context):
            # We must re-enter the profile context in the new thread
            with context:
                # Use random sleeps to interleave clients
                await anyio.sleep(random.random())
                async with PrefectClient(app):
                    await anyio.sleep(random.random())

        threads = [
            threading.Thread(
                target=anyio.run,
                args=(enter_client, prefect.context.SettingsContext.get().copy()),
            )
            for _ in range(100)
        ]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(3)

        assert startup.call_count == shutdown.call_count
        assert startup.call_count > 0

    async def test_client_context_lifespan_is_robust_to_high_async_concurrency(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        async def enter_client():
            # Use random sleeps to interleave clients
            await anyio.sleep(random.random())
            async with PrefectClient(app):
                await anyio.sleep(random.random())

        with anyio.fail_after(15):
            async with anyio.create_task_group() as tg:
                for _ in range(1000):
                    tg.start_soon(enter_client)

        assert startup.call_count == shutdown.call_count
        assert startup.call_count > 0

    @pytest.mark.flaky(max_runs=3)
    @pytest.mark.skipif(not_enough_open_files(), reason=not_enough_open_files.__doc__)
    async def test_client_context_lifespan_is_robust_to_mixed_concurrency(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        async def enter_client():
            # Use random sleeps to interleave clients
            await anyio.sleep(random.random())
            async with PrefectClient(app):
                await anyio.sleep(random.random())

        async def enter_client_many_times(context):
            # We must re-enter the profile context in the new thread
            with context:
                async with anyio.create_task_group() as tg:
                    for _ in range(100):
                        tg.start_soon(enter_client)

        threads = [
            threading.Thread(
                target=anyio.run,
                args=(
                    enter_client_many_times,
                    prefect.context.SettingsContext.get().copy(),
                ),
            )
            for _ in range(100)
        ]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(3)

        assert startup.call_count == shutdown.call_count
        assert startup.call_count > 0

    async def test_client_context_lifespan_is_robust_to_dependency_deadlocks(self):
        """
        If you have two concurrrent contexts which are used as follows:

        --> Context A is entered (manages a new lifespan)
        -----> Context B is entered (uses the lifespan from A)
        -----> Context A exits
        -----> Context B exits

        We must ensure that the lifespan shutdown hooks are not called on exit of A and
        wait for all clients to be done consuming them (e.g. after B exits). We must
        also ensure that we do not deadlock by having dependent waits during this
        interleaved case.
        """
        startup = MagicMock(side_effect=lambda: print("Startup called!"))
        shutdown = MagicMock(side_effect=lambda: print("Shutdown called!!"))

        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        one_started = anyio.Event()
        one_exited = anyio.Event()
        two_started = anyio.Event()

        async def one():
            async with PrefectClient(app):
                print("Started one")
                one_started.set()
                startup.assert_called_once()
                shutdown.assert_not_called()
                print("Waiting for two to start...")
                await two_started.wait()
                # Exit after two has started
                print("Exiting one...")
            one_exited.set()

        async def two():
            await one_started.wait()
            # Enter after one has started but before one has exited
            async with PrefectClient(app):
                print("Started two")
                two_started.set()
                # Wait for one to exit, this creates an interleaved dependency
                await one_exited.wait()
                startup.assert_called_once()
                shutdown.assert_not_called()
                print("Exiting two...")

        # Run concurrently
        with anyio.fail_after(5):  # Kill if a deadlock occurs
            async with anyio.create_task_group() as tg:
                tg.start_soon(one)
                tg.start_soon(two)

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_manages_app_lifespan_on_exception(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        client = PrefectClient(app)

        with pytest.raises(ValueError):
            async with client:
                raise ValueError()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_manages_app_lifespan_on_anyio_cancellation(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        async def enter_client(task_status):
            async with PrefectClient(app):
                task_status.started()
                await anyio.sleep_forever()

        async with anyio.create_task_group() as tg:
            await tg.start(enter_client)
            await tg.start(enter_client)
            await tg.start(enter_client)

            tg.cancel_scope.cancel()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_manages_app_lifespan_on_exception_when_nested(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(lifespan=make_lifespan(startup, shutdown))

        with pytest.raises(ValueError):
            async with PrefectClient(app):
                try:
                    async with PrefectClient(app):
                        raise ValueError()
                finally:
                    # Shutdown not called yet, will be handled by the outermost ctx
                    shutdown.assert_not_called()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_with_without_async_raises_helpful_error(self):
        with pytest.raises(RuntimeError, match="must be entered with an async context"):
            with PrefectClient("http://foo.test"):
                pass


@pytest.mark.parametrize("enabled", [True, False])
async def test_client_runs_migrations_for_ephemeral_app(enabled, monkeypatch):
    with temporary_settings(updates={PREFECT_API_DATABASE_MIGRATE_ON_START: enabled}):
        app = create_app(ephemeral=True, ignore_cache=True)
        mock = AsyncMock()
        monkeypatch.setattr(
            "prefect.server.database.interface.PrefectDBInterface.create_db", mock
        )
        async with PrefectClient(app):
            if enabled:
                mock.assert_awaited_once_with()

        if not enabled:
            mock.assert_not_awaited()


async def test_client_does_not_run_migrations_for_hosted_app(
    hosted_api_server, monkeypatch
):
    with temporary_settings(updates={PREFECT_API_DATABASE_MIGRATE_ON_START: True}):
        mock = AsyncMock()
        monkeypatch.setattr(
            "prefect.server.database.interface.PrefectDBInterface.create_db", mock
        )
        async with PrefectClient(hosted_api_server):
            pass

    mock.assert_not_awaited()


async def test_client_api_url():
    url = PrefectClient("http://foo.test/bar").api_url
    assert isinstance(url, httpx.URL)
    assert str(url) == "http://foo.test/bar/"
    assert PrefectClient(FastAPI()).api_url is not None


async def test_hello(orion_client):
    response = await orion_client.hello()
    assert response.json() == "👋"


async def test_healthcheck(orion_client):
    assert await orion_client.api_healthcheck() is None


async def test_healthcheck_failure(orion_client, monkeypatch):
    monkeypatch.setattr(
        orion_client._client, "get", AsyncMock(side_effect=ValueError("test"))
    )
    assert exceptions_equal(await orion_client.api_healthcheck(), ValueError("test"))


async def test_create_then_read_flow(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    assert isinstance(flow_id, UUID)

    lookup = await orion_client.read_flow(flow_id)
    assert isinstance(lookup, schemas.core.Flow)
    assert lookup.name == foo.name


async def test_create_then_read_deployment(
    orion_client, infrastructure_document_id, storage_document_id
):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        version="git-commit-hash",
        manifest_path="path/file.json",
        schedule=schedule,
        parameters={"foo": "bar"},
        tags=["foo", "bar"],
        infrastructure_document_id=infrastructure_document_id,
        storage_document_id=storage_document_id,
        parameter_openapi_schema={},
    )

    lookup = await orion_client.read_deployment(deployment_id)
    assert isinstance(lookup, schemas.responses.DeploymentResponse)
    assert lookup.name == "test-deployment"
    assert lookup.version == "git-commit-hash"
    assert lookup.manifest_path == "path/file.json"
    assert lookup.schedule == schedule
    assert lookup.parameters == {"foo": "bar"}
    assert lookup.tags == ["foo", "bar"]
    assert lookup.storage_document_id == storage_document_id
    assert lookup.infrastructure_document_id == infrastructure_document_id
    assert lookup.parameter_openapi_schema == {}


async def test_updating_deployment(
    orion_client, infrastructure_document_id, storage_document_id
):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        version="git-commit-hash",
        manifest_path="path/file.json",
        schedule=schedule,
        parameters={"foo": "bar"},
        tags=["foo", "bar"],
        infrastructure_document_id=infrastructure_document_id,
        storage_document_id=storage_document_id,
        parameter_openapi_schema={},
    )

    initial_lookup = await orion_client.read_deployment(deployment_id)
    assert initial_lookup.is_schedule_active
    assert initial_lookup.schedule == schedule

    updated_schedule = IntervalSchedule(interval=timedelta(seconds=86399))  # rude

    await orion_client.update_deployment(
        initial_lookup, schedule=updated_schedule, is_schedule_active=False
    )

    second_lookup = await orion_client.read_deployment(deployment_id)
    assert not second_lookup.is_schedule_active
    assert second_lookup.schedule == updated_schedule


async def test_read_deployment_by_name(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        manifest_path="file.json",
        schedule=schedule,
    )

    lookup = await orion_client.read_deployment_by_name("foo/test-deployment")
    assert isinstance(lookup, schemas.responses.DeploymentResponse)
    assert lookup.id == deployment_id
    assert lookup.name == "test-deployment"
    assert lookup.manifest_path == "file.json"
    assert lookup.schedule == schedule


async def test_create_then_delete_deployment(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        manifest_path="file.json",
        schedule=schedule,
    )

    await orion_client.delete_deployment(deployment_id)
    with pytest.raises(httpx.HTTPStatusError, match="404"):
        await orion_client.read_deployment(deployment_id)


async def test_read_nonexistent_deployment_by_name(orion_client):
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.read_deployment_by_name("not-a-real-deployment")


async def test_create_then_read_concurrency_limit(orion_client):
    cl_id = await orion_client.create_concurrency_limit(
        tag="client-created", concurrency_limit=12345
    )

    lookup = await orion_client.read_concurrency_limit_by_tag("client-created")
    assert lookup.id == cl_id
    assert lookup.concurrency_limit == 12345


async def test_read_nonexistent_concurrency_limit_by_tag(orion_client):
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.read_concurrency_limit_by_tag("not-a-real-tag")


async def test_resetting_concurrency_limits(orion_client):
    cl = await orion_client.create_concurrency_limit(
        tag="an-unimportant-limit", concurrency_limit=100
    )

    await orion_client.reset_concurrency_limit_by_tag(
        "an-unimportant-limit", slot_override=[uuid4(), uuid4(), uuid4()]
    )
    first_lookup = await orion_client.read_concurrency_limit_by_tag(
        "an-unimportant-limit"
    )
    assert len(first_lookup.active_slots) == 3

    await orion_client.reset_concurrency_limit_by_tag("an-unimportant-limit")
    reset_lookup = await orion_client.read_concurrency_limit_by_tag(
        "an-unimportant-limit"
    )
    assert len(reset_lookup.active_slots) == 0


async def test_deleting_concurrency_limits(orion_client):
    cl = await orion_client.create_concurrency_limit(
        tag="dead-limit-walking", concurrency_limit=10
    )

    assert await orion_client.read_concurrency_limit_by_tag("dead-limit-walking")
    await orion_client.delete_concurrency_limit_by_tag("dead-limit-walking")
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.read_concurrency_limit_by_tag("dead-limit-walking")


async def test_create_then_read_flow_run(orion_client):
    @flow
    def foo():
        pass

    flow_run = await orion_client.create_flow_run(
        foo,
        name="zachs-flow-run",
    )
    assert isinstance(flow_run, client_schemas.FlowRun)

    lookup = await orion_client.read_flow_run(flow_run.id)
    # Estimates will not be equal since time has passed
    lookup.estimated_start_time_delta = flow_run.estimated_start_time_delta
    lookup.estimated_run_time = flow_run.estimated_run_time
    assert lookup == flow_run


async def test_create_flow_run_retains_parameters(orion_client):
    @flow
    def foo():
        pass

    parameters = {"x": 1, "y": [1, 2, 3]}

    flow_run = await orion_client.create_flow_run(
        foo, name="zachs-flow-run", parameters=parameters
    )
    assert parameters == flow_run.parameters, "Parameter contents are equal"
    assert id(flow_run.parameters) == id(parameters), "Original objects retained"


async def test_create_flow_run_with_state(orion_client):
    @flow
    def foo():
        pass

    flow_run = await orion_client.create_flow_run(foo, state=Running())
    assert flow_run.state.is_running()


async def test_set_then_read_flow_run_state(orion_client):
    @flow
    def foo():
        pass

    flow_run_id = (await orion_client.create_flow_run(foo)).id
    response = await orion_client.set_flow_run_state(
        flow_run_id,
        state=Completed(message="Test!"),
    )
    assert isinstance(response, OrchestrationResult)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    states = await orion_client.read_flow_run_states(flow_run_id)
    assert len(states) == 2

    assert states[0].is_pending()

    assert states[1].is_completed()
    assert states[1].message == "Test!"


async def test_set_flow_run_state_404_is_object_not_found(orion_client):
    @flow
    def foo():
        pass

    await orion_client.create_flow_run(foo)
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        response = await orion_client.set_flow_run_state(
            uuid4(),
            state=Completed(message="Test!"),
        )


async def test_read_flow_runs_without_filter(orion_client):
    @flow
    def foo():
        pass

    fr_id_1 = (await orion_client.create_flow_run(foo)).id
    fr_id_2 = (await orion_client.create_flow_run(foo)).id

    flow_runs = await orion_client.read_flow_runs()
    assert len(flow_runs) == 2
    assert all(isinstance(flow_run, client_schemas.FlowRun) for flow_run in flow_runs)
    assert {flow_run.id for flow_run in flow_runs} == {fr_id_1, fr_id_2}


async def test_read_flow_runs_with_filtering(orion_client):
    @flow
    def foo():
        pass

    @flow
    def bar():
        pass

    fr_id_1 = (await orion_client.create_flow_run(foo, state=Pending())).id
    fr_id_2 = (await orion_client.create_flow_run(foo, state=Scheduled())).id
    fr_id_3 = (await orion_client.create_flow_run(bar, state=Pending())).id
    # Only below should match the filter
    fr_id_4 = (await orion_client.create_flow_run(bar, state=Scheduled())).id
    fr_id_5 = (await orion_client.create_flow_run(bar, state=Running())).id

    flow_runs = await orion_client.read_flow_runs(
        flow_filter=schemas.filters.FlowFilter(name=dict(any_=["bar"])),
        flow_run_filter=schemas.filters.FlowRunFilter(
            state=dict(
                type=dict(
                    any_=[
                        StateType.SCHEDULED,
                        StateType.RUNNING,
                    ]
                )
            )
        ),
    )
    assert len(flow_runs) == 2
    assert all(isinstance(flow, client_schemas.FlowRun) for flow in flow_runs)
    assert {flow_run.id for flow_run in flow_runs} == {fr_id_4, fr_id_5}


async def test_read_flows_without_filter(orion_client):
    @flow
    def foo():
        pass

    @flow
    def bar():
        pass

    flow_id_1 = await orion_client.create_flow(foo)
    flow_id_2 = await orion_client.create_flow(bar)

    flows = await orion_client.read_flows()
    assert len(flows) == 2
    assert all(isinstance(flow, schemas.core.Flow) for flow in flows)
    assert {flow.id for flow in flows} == {flow_id_1, flow_id_2}


async def test_read_flows_with_filter(orion_client):
    @flow
    def foo():
        pass

    @flow
    def bar():
        pass

    @flow
    def foobar():
        pass

    flow_id_1 = await orion_client.create_flow(foo)
    flow_id_2 = await orion_client.create_flow(bar)
    flow_id_3 = await orion_client.create_flow(foobar)

    flows = await orion_client.read_flows(
        flow_filter=schemas.filters.FlowFilter(name=dict(any_=["foo", "bar"]))
    )
    assert len(flows) == 2
    assert all(isinstance(flow, schemas.core.Flow) for flow in flows)
    assert {flow.id for flow in flows} == {flow_id_1, flow_id_2}


async def test_read_flow_by_name(orion_client):
    @flow(name="null-flow")
    def do_nothing():
        pass

    flow_id = await orion_client.create_flow(do_nothing)
    the_flow = await orion_client.read_flow_by_name("null-flow")

    assert the_flow.id == flow_id


async def test_create_flow_run_from_deployment(orion_client: PrefectClient, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    # Deployment details attached
    assert flow_run.deployment_id == deployment.id
    assert flow_run.flow_id == deployment.flow_id
    assert flow_run.work_queue_name == deployment.work_queue_name
    assert flow_run.work_queue_name  # not empty

    # Flow version is not populated yet
    assert flow_run.flow_version is None
    # State is scheduled for now
    assert flow_run.state.type == StateType.SCHEDULED
    assert (
        pendulum.now("utc")
        .diff(flow_run.state.state_details.scheduled_time)
        .in_seconds()
        < 1
    )


async def test_create_flow_run_from_deployment_idempotency(orion_client, deployment):
    flow_run_1 = await orion_client.create_flow_run_from_deployment(
        deployment.id, idempotency_key="foo"
    )
    flow_run_2 = await orion_client.create_flow_run_from_deployment(
        deployment.id, idempotency_key="foo"
    )

    assert flow_run_2.id == flow_run_1.id

    flow_run_3 = await orion_client.create_flow_run_from_deployment(
        deployment.id, idempotency_key="bar"
    )
    assert flow_run_3.id != flow_run_1.id


async def test_create_flow_run_from_deployment_with_options(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(
        deployment.id,
        name="test-run-name",
        tags={"foo", "bar"},
        state=Pending(message="test"),
        parameters={"foo": "bar"},
    )
    assert flow_run.name == "test-run-name"
    assert set(flow_run.tags) == {"foo", "bar"}.union(deployment.tags)
    assert flow_run.state.type == StateType.PENDING
    assert flow_run.state.message == "test"
    assert flow_run.parameters == {"foo": "bar"}


async def test_update_flow_run(orion_client):
    @flow
    def foo():
        pass

    flow_run = await orion_client.create_flow_run(foo)

    exclude = {"updated", "lateness_estimate", "estimated_start_time_delta"}

    # No mutation for unset fields
    await orion_client.update_flow_run(flow_run.id)
    unchanged_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert unchanged_flow_run.dict(exclude=exclude) == flow_run.dict(exclude=exclude)

    # Fields updated when set
    await orion_client.update_flow_run(
        flow_run.id,
        flow_version="foo",
        parameters={"foo": "bar"},
        name="test",
        tags=["hello", "world"],
        empirical_policy=schemas.core.FlowRunPolicy(
            retries=1,
            retry_delay=2,
        ),
        infrastructure_pid="infrastructure-123:1029",
    )
    updated_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert updated_flow_run.flow_version == "foo"
    assert updated_flow_run.parameters == {"foo": "bar"}
    assert updated_flow_run.name == "test"
    assert updated_flow_run.tags == ["hello", "world"]
    assert updated_flow_run.empirical_policy == schemas.core.FlowRunPolicy(
        retries=1,
        retry_delay=2,
    )
    assert updated_flow_run.infrastructure_pid == "infrastructure-123:1029"


async def test_update_flow_run_overrides_tags(orion_client):
    @flow(name="test_update_flow_run_tags__flow")
    def hello(name):
        return f"Hello {name}"

    with tags("goodbye", "cruel", "world"):
        state = hello("Marvin", return_state=True)

    flow_run = await orion_client.read_flow_run(state.state_details.flow_run_id)

    await orion_client.update_flow_run(
        flow_run.id,
        tags=["hello", "world"],
    )
    updated_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert updated_flow_run.tags == ["hello", "world"]


async def test_create_then_read_task_run(orion_client):
    @flow
    def foo():
        pass

    @task(tags=["a", "b"], retries=3)
    def bar(orion_client):
        pass

    flow_run = await orion_client.create_flow_run(foo)
    task_run = await orion_client.create_task_run(
        bar, flow_run_id=flow_run.id, dynamic_key="0"
    )
    assert isinstance(task_run, schemas.core.TaskRun)

    lookup = await orion_client.read_task_run(task_run.id)
    # Estimates will not be equal since time has passed
    lookup.estimated_start_time_delta = task_run.estimated_start_time_delta
    lookup.estimated_run_time = task_run.estimated_run_time
    assert lookup == task_run


async def test_create_then_read_task_run_with_state(orion_client):
    @flow
    def foo():
        pass

    @task(tags=["a", "b"], retries=3)
    def bar(orion_client):
        pass

    flow_run = await orion_client.create_flow_run(foo)
    task_run = await orion_client.create_task_run(
        bar, flow_run_id=flow_run.id, state=Running(), dynamic_key="0"
    )
    assert task_run.state.is_running()


async def test_set_then_read_task_run_state(orion_client):
    @flow
    def foo():
        pass

    @task
    def bar(orion_client):
        pass

    flow_run = await orion_client.create_flow_run(foo)
    task_run = await orion_client.create_task_run(
        bar, flow_run_id=flow_run.id, dynamic_key="0"
    )

    response = await orion_client.set_task_run_state(
        task_run.id,
        Completed(message="Test!"),
    )

    assert isinstance(response, OrchestrationResult)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    run = await orion_client.read_task_run(task_run.id)
    assert isinstance(run.state, State)
    assert run.state.type == StateType.COMPLETED
    assert run.state.message == "Test!"


async def test_create_then_read_flow_run_notification_policy(
    orion_client, block_document
):
    message_template = "Test message template!"
    state_names = ["COMPLETED"]

    notification_policy_id = await orion_client.create_flow_run_notification_policy(
        block_document_id=block_document.id,
        is_active=True,
        tags=[],
        state_names=state_names,
        message_template=message_template,
    )

    response: List[FlowRunNotificationPolicy] = (
        await orion_client.read_flow_run_notification_policies(
            FlowRunNotificationPolicyFilter(is_active={"eq_": True}),
        )
    )

    assert len(response) == 1
    assert response[0].id == notification_policy_id
    assert response[0].block_document_id == block_document.id
    assert response[0].message_template == message_template
    assert response[0].is_active
    assert response[0].tags == []
    assert response[0].state_names == state_names


async def test_read_filtered_logs(session, orion_client, deployment):
    flow_runs = [uuid4() for i in range(5)]
    logs = [
        LogCreate(
            name="prefect.flow_runs",
            level=20,
            message=f"Log from flow_run {id}.",
            timestamp=datetime.now(tz=timezone.utc),
            flow_run_id=id,
        )
        for id in flow_runs
    ]

    await orion_client.create_logs(logs)

    logs = await orion_client.read_logs(
        log_filter=LogFilter(flow_run_id=LogFilterFlowRunId(any_=flow_runs[:3]))
    )
    for log in logs:
        assert log.flow_run_id in flow_runs[:3]
        assert log.flow_run_id not in flow_runs[3:]


async def test_prefect_api_tls_insecure_skip_verify_setting_set_to_true(monkeypatch):
    with temporary_settings(updates={PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}):
        mock = Mock()
        monkeypatch.setattr("prefect.client.orchestration.PrefectHttpxClient", mock)
        get_client()

    mock.assert_called_once_with(
        headers=ANY,
        verify=False,
        app=ANY,
        base_url=ANY,
        timeout=ANY,
    )


async def test_prefect_api_tls_insecure_skip_verify_setting_set_to_false(monkeypatch):
    with temporary_settings(updates={PREFECT_API_TLS_INSECURE_SKIP_VERIFY: False}):
        mock = Mock()
        monkeypatch.setattr("prefect.client.orchestration.PrefectHttpxClient", mock)
        get_client()

    mock.assert_called_once_with(
        headers=ANY,
        app=ANY,
        base_url=ANY,
        timeout=ANY,
    )


async def test_prefect_api_tls_insecure_skip_verify_default_setting(monkeypatch):
    mock = Mock()
    monkeypatch.setattr("prefect.client.orchestration.PrefectHttpxClient", mock)
    get_client()
    mock.assert_called_once_with(
        headers=ANY,
        app=ANY,
        base_url=ANY,
        timeout=ANY,
    )


class TestResolveDataDoc:
    @pytest.fixture(autouse=True)
    def ignore_deprecation_warnings(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            yield

    async def test_does_not_allow_other_types(self, orion_client):
        with pytest.raises(TypeError, match="invalid type str"):
            await orion_client.resolve_datadoc("foo")

    async def test_resolves_data_document(self, orion_client):
        innermost = await orion_client.resolve_datadoc(
            DataDocument.encode("cloudpickle", "hello")
        )
        assert innermost == "hello"

    async def test_resolves_nested_data_documents(self, orion_client):
        innermost = await orion_client.resolve_datadoc(
            DataDocument.encode("cloudpickle", DataDocument.encode("json", "hello"))
        )
        assert innermost == "hello"

    async def test_resolves_nested_data_documents_when_inner_is_bytes(
        self, orion_client
    ):
        innermost = await orion_client.resolve_datadoc(
            DataDocument.encode(
                "cloudpickle", DataDocument.encode("json", "hello").json().encode()
            )
        )
        assert innermost == "hello"


class TestClientAPIVersionRequests:
    @pytest.fixture
    def versions(self):
        return SERVER_API_VERSION.split(".")

    @pytest.fixture
    def major_version(self, versions):
        return int(versions[0])

    @pytest.fixture
    def minor_version(self, versions):
        return int(versions[1])

    @pytest.fixture
    def patch_version(self, versions):
        return int(versions[2])

    async def test_default_requests_succeeds(self):
        async with get_client() as client:
            res = await client.hello()
            assert res.status_code == status.HTTP_200_OK

    async def test_no_api_version_header_succeeds(self):
        async with get_client() as client:
            # remove default header X-PREFECT-API-VERSION
            client._client.headers = {}
            res = await client.hello()
            assert res.status_code == status.HTTP_200_OK

    async def test_major_version(
        self, app, major_version, minor_version, patch_version
    ):
        # higher client major version works
        api_version = f"{major_version + 1}.{minor_version}.{patch_version}"
        async with PrefectClient(app, api_version=api_version) as client:
            res = await client.hello()
            assert res.status_code == status.HTTP_200_OK

        # lower client major version fails
        api_version = f"{major_version - 1}.{minor_version}.{patch_version}"
        async with PrefectClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

    @pytest.mark.skip(
        reason=(
            "This test is no longer compatible with the current API version checking"
            " logic"
        )
    )
    async def test_minor_version(
        self, app, major_version, minor_version, patch_version
    ):
        # higher client minor version succeeds
        api_version = f"{major_version}.{minor_version + 1}.{patch_version}"
        async with PrefectClient(app, api_version=api_version) as client:
            res = await client.hello()
            assert res.status_code == status.HTTP_200_OK

        # lower client minor version fails
        api_version = f"{major_version}.{minor_version - 1}.{patch_version}"
        async with PrefectClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

    @pytest.mark.skip(
        reason=(
            "This test is no longer compatible with the current API version checking"
            " logic"
        )
    )
    async def test_patch_version(
        self, app, major_version, minor_version, patch_version
    ):
        # higher client patch version succeeds
        api_version = f"{major_version}.{minor_version}.{patch_version + 1}"
        async with PrefectClient(app, api_version=api_version) as client:
            res = await client.hello()
            assert res.status_code == status.HTTP_200_OK

        # lower client patch version fails
        api_version = f"{major_version}.{minor_version}.{patch_version - 1}"
        res = await client.hello()
        async with PrefectClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

    async def test_invalid_header(self, app):
        # Invalid header is rejected
        api_version = "not a real version header"
        async with PrefectClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ) as e:
                await client.hello()
            assert (
                "Invalid X-PREFECT-API-VERSION header format."
                in e.value.response.json()["detail"]
            )


class TestClientAPIKey:
    @pytest.fixture
    async def test_app(self):
        app = FastAPI()
        bearer = HTTPBearer()

        # Returns given credentials if an Authorization
        # header is passed, otherwise raises 403
        @app.get("/api/check_for_auth_header")
        async def check_for_auth_header(credentials=Depends(bearer)):
            return credentials.credentials

        return app

    async def test_client_passes_api_key_as_auth_header(self, test_app):
        api_key = "validAPIkey"
        async with PrefectClient(test_app, api_key=api_key) as client:
            res = await client._client.get("/check_for_auth_header")
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == api_key

    async def test_client_no_auth_header_without_api_key(self, test_app):
        async with PrefectClient(test_app) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_403_FORBIDDEN)
            ) as e:
                await client._client.get("/check_for_auth_header")

    async def test_get_client_includes_api_key_from_context(self):
        with temporary_settings(updates={PREFECT_API_KEY: "test"}):
            client = get_client()

        assert client._client.headers["Authorization"] == "Bearer test"


class TestClientWorkQueues:
    @pytest.fixture
    async def deployment(self, orion_client, infrastructure_document_id):
        foo = flow(lambda: None, name="foo")
        flow_id = await orion_client.create_flow(foo)
        schedule = IntervalSchedule(
            interval=timedelta(days=1), anchor_date=pendulum.datetime(2020, 1, 1)
        )

        deployment_id = await orion_client.create_deployment(
            flow_id=flow_id,
            name="test-deployment",
            manifest_path="file.json",
            schedule=schedule,
            parameters={"foo": "bar"},
            work_queue_name="wq",
            infrastructure_document_id=infrastructure_document_id,
        )
        return deployment_id

    async def test_create_then_read_work_queue(self, orion_client):
        queue = await orion_client.create_work_queue(name="foo")
        assert isinstance(queue.id, UUID)

        lookup = await orion_client.read_work_queue(queue.id)
        assert isinstance(lookup, schemas.core.WorkQueue)
        assert lookup.name == "foo"

    async def test_create_then_read_work_queue_by_name(self, orion_client):
        queue = await orion_client.create_work_queue(name="foo")
        assert isinstance(queue.id, UUID)

        lookup = await orion_client.read_work_queue_by_name("foo")
        assert isinstance(lookup, schemas.core.WorkQueue)
        assert lookup.name == "foo"
        assert lookup.id == queue.id

    async def test_create_then_match_work_queues(self, orion_client):
        await orion_client.create_work_queue(
            name="one of these things is not like the other"
        )
        await orion_client.create_work_queue(
            name="one of these things just doesn't belong"
        )
        await orion_client.create_work_queue(
            name="can you tell which thing is not like the others"
        )
        matched_queues = await orion_client.match_work_queues(["one of these things"])
        assert len(matched_queues) == 2

    async def test_read_nonexistant_work_queue(self, orion_client):
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await orion_client.read_work_queue_by_name("foo")

    async def test_create_work_queue_with_tags_deprecated(self, orion_client):
        with pytest.deprecated_call():
            await orion_client.create_work_queue(name="test-queue", tags=["a"])

    async def test_get_runs_from_queue_includes(
        self, session, orion_client, deployment
    ):
        wq_1 = await orion_client.read_work_queue_by_name(name="wq")
        wq_2 = await orion_client.create_work_queue(name="wq2")

        run = await orion_client.create_flow_run_from_deployment(deployment)
        assert run.id

        runs_1 = await orion_client.get_runs_in_work_queue(wq_1.id)
        assert runs_1 == [run]

        runs_2 = await orion_client.get_runs_in_work_queue(wq_2.id)
        assert runs_2 == []

    async def test_get_runs_from_queue_respects_limit(self, orion_client, deployment):
        queue = await orion_client.read_work_queue_by_name(name="wq")

        runs = []
        for _ in range(10):
            run = await orion_client.create_flow_run_from_deployment(deployment)
            runs.append(run)

        output = await orion_client.get_runs_in_work_queue(queue.id, limit=1)
        assert len(output) == 1
        assert output[0].id in [r.id for r in runs]

        output = await orion_client.get_runs_in_work_queue(queue.id, limit=8)
        assert len(output) == 8
        assert {o.id for o in output} < {r.id for r in runs}

        output = await orion_client.get_runs_in_work_queue(queue.id, limit=20)
        assert len(output) == 10
        assert {o.id for o in output} == {r.id for r in runs}


async def test_delete_flow_run(orion_client, flow_run):
    # Note - the flow_run provided by the fixture is not of type `schemas.core.FlowRun`
    print(f"Type: {type(flow_run)}")

    # Make sure our flow exists (the read flow is of type `s.c.FlowRun`)
    lookup = await orion_client.read_flow_run(flow_run.id)
    assert isinstance(lookup, client_schemas.FlowRun)

    # Check delete works
    await orion_client.delete_flow_run(flow_run.id)
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.read_flow_run(flow_run.id)

    # Check that trying to delete the deleted flow run raises an error
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.delete_flow_run(flow_run.id)


def test_server_type_ephemeral(orion_client):
    assert orion_client.server_type == ServerType.EPHEMERAL


async def test_server_type_server(hosted_api_server):
    async with PrefectClient(hosted_api_server) as orion_client:
        assert orion_client.server_type == ServerType.SERVER


async def test_server_type_cloud():
    async with PrefectClient(PREFECT_CLOUD_API_URL.value()) as orion_client:
        assert orion_client.server_type == ServerType.CLOUD


@pytest.mark.parametrize(
    "on_create, expected_value", [(True, True), (False, False), (None, True)]
)
async def test_update_deployment_schedule_active_does_not_overwrite_when_not_provided(
    orion_client, flow_run, on_create, expected_value
):
    deployment_id = await orion_client.create_deployment(
        flow_id=flow_run.flow_id,
        name="test-deployment",
        manifest_path="file.json",
        parameters={"foo": "bar"},
        work_queue_name="wq",
        is_schedule_active=on_create,
    )
    # Check that is_schedule_active is created as expected
    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.is_schedule_active == expected_value

    # Check that updating the deployment without providing is_schedule_active does not modify the value
    schedule = IntervalSchedule(interval=timedelta(days=1))
    await orion_client.update_deployment(deployment, schedule=schedule)
    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.is_schedule_active == expected_value


@pytest.mark.parametrize(
    "on_create, after_create, on_update, after_update",
    [
        (False, False, True, True),
        (True, True, False, False),
        (None, True, False, False),
    ],
)
async def test_update_deployment_schedule_active_overwrites_when_provided(
    orion_client,
    flow_run,
    on_create,
    after_create,
    on_update,
    after_update,
):
    deployment_id = await orion_client.create_deployment(
        flow_id=flow_run.flow_id,
        name="test-deployment",
        manifest_path="file.json",
        parameters={"foo": "bar"},
        work_queue_name="wq",
        is_schedule_active=on_create,
    )
    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.is_schedule_active == after_create

    await orion_client.update_deployment(deployment, is_schedule_active=on_update)
    deployment = await orion_client.read_deployment(deployment_id)
    assert deployment.is_schedule_active == after_update


class TestWorkPools:
    async def test_read_work_pools(self, orion_client):
        # default pool shows up when running the test class or individuals, but not when running
        # test as a module
        pools = await orion_client.read_work_pools()
        existing_name = set([p.name for p in pools])
        existing_ids = set([p.id for p in pools])
        default_agent_pool_name = "default-agent-pool"
        work_pool_1 = await orion_client.create_work_pool(
            work_pool=WorkPoolCreate(name="test-pool-1")
        )
        work_pool_2 = await orion_client.create_work_pool(
            work_pool=WorkPoolCreate(name="test-pool-2")
        )
        pools = await orion_client.read_work_pools()
        names_after_adding = set([p.name for p in pools])
        ids_after_adding = set([p.id for p in pools])
        assert names_after_adding.symmetric_difference(existing_name) == {
            work_pool_1.name,
            work_pool_2.name,
        }
        assert ids_after_adding.symmetric_difference(existing_ids) == {
            work_pool_1.id,
            work_pool_2.id,
        }

    async def test_delete_work_pool(self, orion_client, work_pool):
        await orion_client.delete_work_pool(work_pool.name)
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await orion_client.read_work_pool(work_pool.id)


class TestArtifacts:
    @pytest.fixture
    async def artifacts(self, orion_client):
        artifact1 = await orion_client.create_artifact(
            artifact=ArtifactCreate(
                key="voltaic",
                data=1,
                type="table",
                description="# This is a markdown description title",
            )
        )
        artifact2 = await orion_client.create_artifact(
            artifact=ArtifactCreate(
                key="voltaic",
                data=2,
                type="table",
                description="# This is a markdown description title",
            )
        )
        artifact3 = await orion_client.create_artifact(
            artifact=ArtifactCreate(
                key="lotus",
                data=3,
                type="markdown",
                description="# This is a markdown description title",
            )
        )

        return [artifact1, artifact2, artifact3]

    async def test_create_then_read_artifact(self, orion_client, client):
        artifact_schema = ArtifactCreate(
            key="voltaic",
            data=1,
            description="# This is a markdown description title",
            metadata_={"data": "opens many doors"},
        )
        artifact = await orion_client.create_artifact(artifact=artifact_schema)
        response = await client.get(f"/artifacts/{artifact.id}")
        assert response.status_code == 200
        assert response.json()["key"] == artifact.key
        assert response.json()["description"] == artifact.description

    async def test_read_artifacts(self, orion_client, artifacts):
        artifact_list = await orion_client.read_artifacts()
        assert len(artifact_list) == 3
        keyed_data = {(r.key, r.data) for r in artifact_list}
        assert keyed_data == {
            ("voltaic", 1),
            ("voltaic", 2),
            ("lotus", 3),
        }

    async def test_read_artifacts_with_latest_filter(self, orion_client, artifacts):
        artifact_list = await orion_client.read_latest_artifacts()

        assert len(artifact_list) == 2
        keyed_data = {(r.key, r.data) for r in artifact_list}
        assert keyed_data == {
            ("voltaic", 2),
            ("lotus", 3),
        }

    async def test_read_artifacts_with_key_filter(self, orion_client, artifacts):
        key_artifact_filter = schemas.filters.ArtifactFilter(
            key=schemas.filters.ArtifactFilterKey(any_=["voltaic"])
        )

        artifact_list = await orion_client.read_artifacts(
            artifact_filter=key_artifact_filter
        )

        assert len(artifact_list) == 2
        keyed_data = {(r.key, r.data) for r in artifact_list}
        assert keyed_data == {
            ("voltaic", 1),
            ("voltaic", 2),
        }

    async def test_delete_artifact_succeeds(self, orion_client, artifacts):
        await orion_client.delete_artifact(artifacts[1].id)
        artifact_list = await orion_client.read_artifacts()
        assert len(artifact_list) == 2
        keyed_data = {(r.key, r.data) for r in artifact_list}
        assert keyed_data == {
            ("voltaic", 1),
            ("lotus", 3),
        }

    async def test_delete_nonexistent_artifact_raises(self, orion_client):
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await orion_client.delete_artifact(uuid4())


class TestVariables:
    @pytest.fixture
    async def variable(
        self,
        client,
    ):
        res = await client.post(
            "/variables/",
            json=schemas.actions.VariableCreate(
                name="my_variable", value="my-value", tags=["123", "456"]
            ).dict(json_compatible=True),
        )
        assert res.status_code == 201
        return pydantic.parse_obj_as(schemas.core.Variable, res.json())

    @pytest.fixture
    async def variables(
        self,
        client,
    ):
        variables = [
            schemas.actions.VariableCreate(
                name="my_variable1", value="my-value1", tags=["1"]
            ),
            schemas.actions.VariableCreate(
                name="my_variable2", value="my-value2", tags=["2"]
            ),
            schemas.actions.VariableCreate(
                name="my_variable3", value="my-value3", tags=["3"]
            ),
        ]
        results = []
        for variable in variables:
            res = await client.post(
                "/variables/", json=variable.dict(json_compatible=True)
            )
            assert res.status_code == 201
            results.append(res.json())
        return pydantic.parse_obj_as(List[schemas.core.Variable], results)

    async def test_read_variable_by_name(self, orion_client, variable):
        res = await orion_client.read_variable_by_name(variable.name)
        assert res.name == variable.name
        assert res.value == variable.value
        assert res.tags == variable.tags

    async def test_read_variable_by_name_doesnt_exist(self, orion_client):
        res = await orion_client.read_variable_by_name("doesnt_exist")
        assert res is None

    async def test_delete_variable_by_name(self, orion_client, variable):
        await orion_client.delete_variable_by_name(variable.name)
        res = await orion_client.read_variable_by_name(variable.name)
        assert not res

    async def test_delete_variable_by_name_doesnt_exist(self, orion_client):
        with pytest.raises(prefect.exceptions.ObjectNotFound):
            await orion_client.delete_variable_by_name("doesnt_exist")

    async def test_read_variables(self, orion_client, variables):
        res = await orion_client.read_variables()
        assert len(res) == len(variables)
        assert {r.name for r in res} == {v.name for v in variables}

    async def test_read_variables_with_limit(self, orion_client, variables):
        res = await orion_client.read_variables(limit=1)
        assert len(res) == 1
        assert res[0].name == variables[0].name
