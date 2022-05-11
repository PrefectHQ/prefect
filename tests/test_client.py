import random
import threading
from dataclasses import dataclass
from datetime import timedelta
from unittest.mock import MagicMock, call
from uuid import UUID

import anyio
import httpx
import pendulum
import pytest
from fastapi import Depends, FastAPI, status
from fastapi.security import HTTPBearer
from httpx import AsyncClient, HTTPStatusError, Request, Response
from pydantic import BaseModel

import prefect.context
import prefect.exceptions
from prefect import flow
from prefect.client import OrionClient, PrefectHttpxClient, get_client
from prefect.flow_runners import UniversalFlowRunner
from prefect.orion import schemas
from prefect.orion.api.server import ORION_API_VERSION, create_app
from prefect.orion.orchestration.rules import OrchestrationResult
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.schedules import IntervalSchedule
from prefect.orion.schemas.states import Pending, Running, Scheduled, StateType
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_LOGGING_LEVEL,
    PREFECT_ORION_DATABASE_MIGRATE_ON_START,
    temporary_settings,
)
from prefect.tasks import task
from prefect.testing.utilities import AsyncMock, exceptions_equal


class TestPrefectHttpxClient:
    async def test_prefect_httpx_client_retries_429s(self, monkeypatch):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()
        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": "0"},
            request=Request("a test request", "fake.url/fake/route"),
        )
        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )
        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            success_response,
        ]
        response = await client.post(
            url="fake.url/fake/route", data={"evenmorefake": "data"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert base_client_send.call_count == 4

    async def test_prefect_httpx_client_retries_429s_up_to_five_times(
        self, monkeypatch
    ):
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": "0"},
            request=Request("a test request", "fake.url/fake/route"),
        )

        # Return more than 6 retry responses
        base_client_send.side_effect = [retry_response] * 7

        with pytest.raises(HTTPStatusError, match="429"):
            await client.post(
                url="fake.url/fake/route",
                data={"evenmorefake": "data"},
            )

        # 5 retries + 1 first attempt
        assert base_client_send.call_count == 6

    async def test_prefect_httpx_client_respects_retry_header(self, monkeypatch):
        sleep = AsyncMock()
        monkeypatch.setattr(anyio, "sleep", sleep)
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()
        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": "5"},
            request=Request("a test request", "fake.url/fake/route"),
        )

        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            retry_response,
            success_response,
        ]

        response = await client.post(
            url="fake.url/fake/route", data={"evenmorefake": "data"}
        )
        assert response.status_code == status.HTTP_200_OK
        sleep.assert_awaited_once_with(5)

    async def test_prefect_httpx_client_falls_back_to_exponential_backoff(
        self, monkeypatch
    ):
        sleep = AsyncMock()
        monkeypatch.setattr(anyio, "sleep", sleep)
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()
        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            request=Request("a test request", "fake.url/fake/route"),
        )

        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            success_response,
        ]

        response = await client.post(
            url="fake.url/fake/route", data={"evenmorefake": "data"}
        )
        assert response.status_code == status.HTTP_200_OK
        sleep.assert_has_awaits([call(2), call(4), call(8)])

    async def test_prefect_httpx_client_respects_retry_header_per_response(
        self, monkeypatch
    ):
        sleep = AsyncMock()
        monkeypatch.setattr(anyio, "sleep", sleep)
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        def make_retry_response(retry_after):
            return Response(
                status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                request=Request("a test request", "fake.url/fake/route"),
            )

        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            make_retry_response(5),
            make_retry_response(0),
            make_retry_response(10),
            make_retry_response(2.0),
            success_response,
        ]

        response = await client.post(
            url="fake.url/fake/route", data={"evenmorefake": "data"}
        )
        assert response.status_code == status.HTTP_200_OK
        sleep.assert_has_awaits([call(5), call(0), call(10), call(2.0)])


class TestGetClient:
    def test_get_client_returns_client(self):
        assert isinstance(get_client(), OrionClient)

    def test_get_client_does_not_cache_client(self):
        assert get_client() is not get_client()

    def test_get_client_cache_uses_profile_settings(self):
        client = get_client()
        with temporary_settings(updates={PREFECT_LOGGING_LEVEL: "FOO"}):
            new_client = get_client()
            assert isinstance(new_client, OrionClient)
            assert new_client is not client


class TestClientContextManager:
    async def test_client_context_cannot_be_reentered(self):
        client = OrionClient("http://foo.test")
        async with client:
            with pytest.raises(RuntimeError, match="cannot be started more than once"):
                async with client:
                    pass

    async def test_client_context_cannot_be_reused(self):
        client = OrionClient("http://foo.test")
        async with client:
            pass

        with pytest.raises(RuntimeError, match="cannot be started again after closing"):
            async with client:
                pass

    async def test_client_context_manages_app_lifespan(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        client = OrionClient(app)
        startup.assert_not_called()
        shutdown.assert_not_called()

        async with client:
            startup.assert_called_once()
            shutdown.assert_not_called()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_calls_app_lifespan_once_despite_nesting(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        startup.assert_not_called()
        shutdown.assert_not_called()

        async with OrionClient(app):
            async with OrionClient(app):
                async with OrionClient(app):
                    startup.assert_called_once()
            shutdown.assert_not_called()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_manages_app_lifespan_on_sequential_usage(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        async with OrionClient(app):
            pass

        assert startup.call_count == 1
        assert shutdown.call_count == 1

        async with OrionClient(app):
            assert startup.call_count == 2
            assert shutdown.call_count == 1

        assert startup.call_count == 2
        assert shutdown.call_count == 2

    async def test_client_context_lifespan_is_robust_to_async_concurrency(self):
        startup = MagicMock(side_effect=lambda: print("Startup called!"))
        shutdown = MagicMock(side_effect=lambda: print("Shutdown called!!"))

        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        one_started = anyio.Event()
        one_exited = anyio.Event()
        two_started = anyio.Event()

        async def one():
            async with OrionClient(app):
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
            async with OrionClient(app):
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

    async def test_client_context_lifespan_is_robust_to_threaded_concurrency(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        async def enter_client(context):
            # We must re-enter the profile context in the new thread
            with context:
                # Use random sleeps to interleave clients
                await anyio.sleep(random.random())
                async with OrionClient(app):
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
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        async def enter_client():
            # Use random sleeps to interleave clients
            await anyio.sleep(random.random())
            async with OrionClient(app):
                await anyio.sleep(random.random())

        with anyio.fail_after(5):
            async with anyio.create_task_group() as tg:
                for _ in range(1000):
                    tg.start_soon(enter_client)

        assert startup.call_count == shutdown.call_count
        assert startup.call_count > 0

    async def test_client_context_lifespan_is_robust_to_mixed_concurrency(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        async def enter_client():
            # Use random sleeps to interleave clients
            await anyio.sleep(random.random())
            async with OrionClient(app):
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

        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        one_started = anyio.Event()
        one_exited = anyio.Event()
        two_started = anyio.Event()

        async def one():
            async with OrionClient(app):
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
            async with OrionClient(app):
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
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        client = OrionClient(app)

        with pytest.raises(ValueError):
            async with client:
                raise ValueError()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_client_context_manages_app_lifespan_on_anyio_cancellation(self):
        startup, shutdown = MagicMock(), MagicMock()
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        async def enter_client(task_status):
            async with OrionClient(app):
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
        app = FastAPI(on_startup=[startup], on_shutdown=[shutdown])

        with pytest.raises(ValueError):
            async with OrionClient(app):
                try:
                    async with OrionClient(app):
                        raise ValueError()
                finally:
                    # Shutdown not called yet, will be handled by the outermost ctx
                    shutdown.assert_not_called()

        startup.assert_called_once()
        shutdown.assert_called_once()

    async def test_with_without_async_raises_helpful_error(self):
        with pytest.raises(RuntimeError, match="must be entered with an async context"):
            with OrionClient("http://foo.test"):
                pass


@pytest.mark.parametrize("enabled", [True, False])
async def test_client_runs_migrations_for_ephemeral_app(enabled, monkeypatch):
    with temporary_settings(updates={PREFECT_ORION_DATABASE_MIGRATE_ON_START: enabled}):
        app = create_app(ephemeral=True, ignore_cache=True)
        mock = AsyncMock()
        monkeypatch.setattr(
            "prefect.orion.database.interface.OrionDBInterface.create_db", mock
        )
        async with OrionClient(app):
            if enabled:
                mock.assert_awaited_once_with()

        if not enabled:
            mock.assert_not_awaited()


async def test_client_does_not_run_migrations_for_hosted_app(
    hosted_orion_api, monkeypatch
):
    with temporary_settings(updates={PREFECT_ORION_DATABASE_MIGRATE_ON_START: True}):
        mock = AsyncMock()
        monkeypatch.setattr(
            "prefect.orion.database.interface.OrionDBInterface.create_db", mock
        )
        async with OrionClient(hosted_orion_api):
            pass

    mock.assert_not_awaited()


async def test_client_api_url():
    url = OrionClient("http://foo.test/bar").api_url
    assert isinstance(url, httpx.URL)
    assert str(url) == "http://foo.test/bar/"
    assert OrionClient(FastAPI()).api_url is not None


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


async def test_create_then_read_deployment(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))
    flow_data = DataDocument.encode("cloudpickle", foo)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        flow_data=flow_data,
        schedule=schedule,
        parameters={"foo": "bar"},
        tags=["foo", "bar"],
        flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
    )

    lookup = await orion_client.read_deployment(deployment_id)
    assert isinstance(lookup, schemas.core.Deployment)
    assert lookup.name == "test-deployment"
    assert lookup.flow_data == flow_data
    assert lookup.schedule == schedule
    assert lookup.parameters == {"foo": "bar"}
    assert lookup.tags == ["foo", "bar"]
    assert lookup.flow_runner == UniversalFlowRunner(env={"foo": "bar"}).to_settings()


async def test_read_deployment_by_name(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))
    flow_data = DataDocument.encode("cloudpickle", foo)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        flow_data=flow_data,
        schedule=schedule,
    )

    lookup = await orion_client.read_deployment_by_name("foo/test-deployment")
    assert isinstance(lookup, schemas.core.Deployment)
    assert lookup.id == deployment_id
    assert lookup.name == "test-deployment"
    assert lookup.flow_data == flow_data
    assert lookup.schedule == schedule


async def test_create_then_delete_deployment(orion_client):
    @flow
    def foo():
        pass

    flow_id = await orion_client.create_flow(foo)
    schedule = IntervalSchedule(interval=timedelta(days=1))
    flow_data = DataDocument.encode("cloudpickle", foo)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="test-deployment",
        flow_data=flow_data,
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
        foo, name="zachs-flow-run", flow_runner=UniversalFlowRunner(env={"foo": "bar"})
    )
    assert isinstance(flow_run, schemas.core.FlowRun)

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

    flow_run = await orion_client.create_flow_run(foo, state=schemas.states.Running())
    assert flow_run.state.is_running()


async def test_set_then_read_flow_run_state(orion_client):
    @flow
    def foo():
        pass

    flow_run_id = (await orion_client.create_flow_run(foo)).id
    response = await orion_client.set_flow_run_state(
        flow_run_id,
        state=schemas.states.Completed(message="Test!"),
    )
    assert isinstance(response, OrchestrationResult)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    states = await orion_client.read_flow_run_states(flow_run_id)
    assert len(states) == 2

    assert states[0].is_pending()

    assert states[1].is_completed()
    assert states[1].message == "Test!"


async def test_read_flow_runs_without_filter(orion_client):
    @flow
    def foo():
        pass

    fr_id_1 = (await orion_client.create_flow_run(foo)).id
    fr_id_2 = (await orion_client.create_flow_run(foo)).id

    flow_runs = await orion_client.read_flow_runs()
    assert len(flow_runs) == 2
    assert all(isinstance(flow_run, schemas.core.FlowRun) for flow_run in flow_runs)
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
    assert all(isinstance(flow, schemas.core.FlowRun) for flow in flow_runs)
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


async def test_create_flow_run_from_deployment(orion_client, deployment):
    flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)
    # Deployment details attached
    assert flow_run.deployment_id == deployment.id
    assert flow_run.flow_id == deployment.flow_id
    # Includes flow runner
    assert flow_run.flow_runner.dict() == deployment.flow_runner.dict()
    # Flow version is not populated yet
    assert flow_run.flow_version is None
    # State is scheduled for now
    assert flow_run.state.type == schemas.states.StateType.SCHEDULED
    assert (
        pendulum.now("utc")
        .diff(flow_run.state.state_details.scheduled_time)
        .in_seconds()
        < 1
    )


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
        flow_run.id, flow_version="foo", parameters={"foo": "bar"}, name="test"
    )
    updated_flow_run = await orion_client.read_flow_run(flow_run.id)
    assert updated_flow_run.flow_version == "foo"
    assert updated_flow_run.parameters == {"foo": "bar"}
    assert updated_flow_run.name == "test"


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
        bar, flow_run_id=flow_run.id, state=schemas.states.Running(), dynamic_key="0"
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
        schemas.states.Completed(message="Test!"),
    )

    assert isinstance(response, OrchestrationResult)
    assert response.status == schemas.responses.SetStateStatus.ACCEPT

    run = await orion_client.read_task_run(task_run.id)
    assert isinstance(run.state, schemas.states.State)
    assert run.state.type == schemas.states.StateType.COMPLETED
    assert run.state.message == "Test!"


@dataclass
class ExDataClass:
    x: int


class ExPydanticModel(BaseModel):
    x: int


@pytest.mark.parametrize(
    "put_obj",
    [
        "hello",
        7,
        ExDataClass(x=1),
        ExPydanticModel(x=0),
    ],
)
async def test_put_then_retrieve_object(put_obj, orion_client, local_storage_block):
    data_document = await orion_client.persist_object(
        put_obj, storage_block=local_storage_block
    )
    assert isinstance(data_document, DataDocument)
    retrieved_obj = await orion_client.retrieve_object(data_document)
    assert retrieved_obj == put_obj


class TestResolveDataDoc:
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

    async def test_resolves_persisted_data_documents(
        self, orion_client, local_storage_block
    ):
        innermost = await orion_client.resolve_datadoc(
            (
                await orion_client.persist_data(
                    DataDocument.encode("json", "hello").json().encode(),
                    block=local_storage_block,
                )
            ),
        )
        assert innermost == "hello"


class TestClientAPIVersionRequests:
    @pytest.fixture
    def versions(self):
        return ORION_API_VERSION.split(".")

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
        # higher client major version fails
        api_version = f"{major_version + 1}.{minor_version}.{patch_version}"
        async with OrionClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

        # lower client major version fails
        api_version = f"{major_version + 1}.{minor_version}.{patch_version}"
        async with OrionClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

    async def test_minor_version(
        self, app, major_version, minor_version, patch_version
    ):
        # higher client minor version fails
        api_version = f"{major_version}.{minor_version + 1}.{patch_version}"
        async with OrionClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

        # lower client minor version fails
        api_version = f"{major_version}.{minor_version - 1}.{patch_version}"
        async with OrionClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

    async def test_patch_version(
        self, app, major_version, minor_version, patch_version
    ):
        # higher client patch version fails
        api_version = f"{major_version}.{minor_version}.{patch_version + 1}"
        async with OrionClient(app, api_version=api_version) as client:
            with pytest.raises(
                httpx.HTTPStatusError, match=str(status.HTTP_400_BAD_REQUEST)
            ):
                await client.hello()

        # lower client minor version succeeds
        api_version = f"{major_version}.{minor_version}.{patch_version - 1}"
        async with OrionClient(app, api_version=api_version) as client:
            res = await client.hello()
            assert res.status_code == status.HTTP_200_OK

    async def test_invalid_header(self, app):
        # Invalid header is rejected
        api_version = "not a real version header"
        async with OrionClient(app, api_version=api_version) as client:
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
        async with OrionClient(test_app, api_key=api_key) as client:
            res = await client._client.get("/check_for_auth_header")
        assert res.status_code == status.HTTP_200_OK
        assert res.json() == api_key

    async def test_client_no_auth_header_without_api_key(self, test_app):
        async with OrionClient(test_app) as client:
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
    async def deployment(self, orion_client):
        foo = flow(lambda: None, name="foo")
        flow_id = await orion_client.create_flow(foo)
        schedule = IntervalSchedule(interval=timedelta(days=1))
        flow_data = DataDocument.encode("cloudpickle", foo)

        deployment_id = await orion_client.create_deployment(
            flow_id=flow_id,
            name="test-deployment",
            flow_data=flow_data,
            schedule=schedule,
            parameters={"foo": "bar"},
            tags=["bing", "bang"],
            flow_runner=UniversalFlowRunner(env={"foo": "bar"}),
        )
        return deployment_id

    async def test_create_then_read_work_queue(self, orion_client):
        queue_id = await orion_client.create_work_queue(name="foo")
        assert isinstance(queue_id, UUID)

        lookup = await orion_client.read_work_queue(queue_id)
        assert isinstance(lookup, schemas.core.WorkQueue)
        assert lookup.name == "foo"

    async def test_create_then_read_work_queue_by_name(self, orion_client):
        queue_id = await orion_client.create_work_queue(name="foo")
        assert isinstance(queue_id, UUID)

        lookup = await orion_client.read_work_queue_by_name("foo")
        assert isinstance(lookup, schemas.core.WorkQueue)
        assert lookup.name == "foo"
        assert lookup.id == queue_id

    async def test_read_nonexistant_work_queue(self, orion_client):
        with pytest.raises(httpx.HTTPStatusError):
            await orion_client.read_work_queue_by_name("foo")

    async def test_get_runs_from_queue_includes(self, orion_client, deployment):
        blank_queue_id = await orion_client.create_work_queue(name="blank")
        assert isinstance(blank_queue_id, UUID)

        tagged_queue_id = await orion_client.create_work_queue(
            name="tagged", tags=["bing", "bang"]
        )
        assert isinstance(tagged_queue_id, UUID)

        deploy_queue_id = await orion_client.create_work_queue(
            name="deploy", deployment_ids=[deployment]
        )
        assert isinstance(deploy_queue_id, UUID)

        run = await orion_client.create_flow_run_from_deployment(deployment)
        assert run.id

        blank_output = await orion_client.get_runs_in_work_queue(blank_queue_id)
        assert blank_output == [run]

        tagged_output = await orion_client.get_runs_in_work_queue(tagged_queue_id)
        assert tagged_output == [run]

        deploy_output = await orion_client.get_runs_in_work_queue(deploy_queue_id)
        assert deploy_output == [run]

    async def test_get_runs_from_queue_excludes(self, orion_client, deployment):
        blank_queue_id = await orion_client.create_work_queue(name="blank")
        assert isinstance(blank_queue_id, UUID)

        tagged_queue_id = await orion_client.create_work_queue(
            name="tagged", tags=["bing", "bazz"]
        )
        assert isinstance(tagged_queue_id, UUID)

        deploy_queue_id = await orion_client.create_work_queue(
            name="deploy", deployment_ids=[tagged_queue_id]  # nonsensical
        )
        assert isinstance(deploy_queue_id, UUID)

        run = await orion_client.create_flow_run_from_deployment(deployment)
        assert run.id

        blank_output = await orion_client.get_runs_in_work_queue(blank_queue_id)
        assert blank_output == [run]

        tagged_output = await orion_client.get_runs_in_work_queue(tagged_queue_id)
        assert tagged_output == []

        deploy_output = await orion_client.get_runs_in_work_queue(deploy_queue_id)
        assert deploy_output == []

    async def test_get_runs_from_queue_respects_limit(self, orion_client, deployment):
        queue_id = await orion_client.create_work_queue(
            name="deploy", deployment_ids=[deployment]
        )

        runs = []
        for _ in range(10):
            run = await orion_client.create_flow_run_from_deployment(deployment)
            runs.append(run)

        output = await orion_client.get_runs_in_work_queue(queue_id, limit=1)
        assert len(output) == 1
        assert output[0].id in [r.id for r in runs]

        output = await orion_client.get_runs_in_work_queue(queue_id, limit=8)
        assert len(output) == 8
        assert {o.id for o in output} < {r.id for r in runs}

        output = await orion_client.get_runs_in_work_queue(queue_id, limit=20)
        assert len(output) == 10
        assert {o.id for o in output} == {r.id for r in runs}
