import uuid
import warnings
from typing import Callable, Generator, List
from unittest import mock

import pydantic
import pytest
from fastapi.testclient import TestClient

from prefect import flow
from prefect._internal.compatibility.deprecated import PrefectDeprecationWarning
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import FlowRun
from prefect.runner import Runner
from prefect.runner.server import build_server
from prefect.settings import (
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_PORT,
    temporary_settings,
)


class A(pydantic.BaseModel):
    a: int = 0


class B(pydantic.BaseModel):
    a: A = A()
    b: bool = False


@flow(version="test")
def simple_flow(verb: str = "party"):
    print(f"I'm just here to {verb}")


@flow
def complex_flow(
    x: int, y: str = "hello", z: List[bool] = [True], a: A = A(), b: B = B()
):
    print(x, y, z, a, b)


def a_non_flow_function():
    print("This is not a flow!")


@pytest.fixture(autouse=True)
def tmp_runner_settings():
    with temporary_settings(
        updates={
            PREFECT_RUNNER_SERVER_HOST: "0.0.0.0",
            PREFECT_RUNNER_SERVER_PORT: 0,
        }
    ):
        yield


@pytest.fixture(autouse=True)
def suppress_deprecation_warnings() -> Generator[None, None, None]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PrefectDeprecationWarning)
        yield


@pytest.fixture
async def runner() -> Runner:
    return Runner()


async def create_deployment(runner: Runner, func: Callable):
    # Use unique names to force multiple deployments to be created
    deployment_id = await runner.add_flow(
        func, f"{uuid.uuid4()}", enforce_parameter_schema=True
    )
    return str(deployment_id)


class TestWebserverSettings:
    async def test_webserver_settings_are_respected(self, runner: Runner):
        with temporary_settings(
            updates={
                PREFECT_RUNNER_SERVER_HOST: "127.0.0.1",
                PREFECT_RUNNER_SERVER_PORT: 4200,
            }
        ):
            assert PREFECT_RUNNER_SERVER_HOST.value() == "127.0.0.1"
            assert PREFECT_RUNNER_SERVER_PORT.value() == 4200


class TestWebserverDeploymentRoutes:
    async def test_runners_deployment_run_routes_exist(self, runner: Runner):
        deployment_ids = [
            await create_deployment(runner, simple_flow) for _ in range(3)
        ]
        webserver = await build_server(runner)

        deployment_run_routes = [
            r
            for r in webserver.routes
            if r.path.startswith("/deployment") and r.path.endswith("/run")
        ]
        deployment_run_paths = {r.path for r in deployment_run_routes}

        # verify that all deployment routes correspond to one of the deployments
        for route in deployment_run_routes:
            id_ = route.path.split("/")[2]
            assert id_ in deployment_ids

        # verify that all deployments have a route
        for id_ in deployment_ids:
            route = f"/deployment/{id_}/run"
            assert route in deployment_run_paths

    @pytest.mark.skip(reason="This test is flaky and needs to be fixed")
    async def test_runners_deployment_run_route_does_input_validation(
        self, runner: Runner
    ):
        async with runner:
            deployment_id = await create_deployment(runner, simple_flow)
            webserver = await build_server(runner)

            client = TestClient(webserver)
            response = client.post(
                f"/deployment/{deployment_id}/run", json={"verb": False}
            )
            assert response.status_code == 400

            response = client.post(
                f"/deployment/{deployment_id}/run", json={"verb": "clobber"}
            )
            assert response.status_code == 201
            flow_run_id = response.json()["flow_run_id"]
            assert isinstance(uuid.UUID(flow_run_id), uuid.UUID)

    @pytest.mark.skip(reason="This test is flaky and needs to be fixed")
    async def test_runners_deployment_run_route_with_complex_args(self, runner: Runner):
        async with runner:
            deployment_id = await runner.add_flow(
                complex_flow, f"{uuid.uuid4()}", enforce_parameter_schema=True
            )
            webserver = await build_server(runner)
            client = TestClient(webserver)
            response = client.post(f"/deployment/{deployment_id}/run", json={"x": 100})
            assert response.status_code == 201, response.json()
            flow_run_id = response.json()["flow_run_id"]
            assert isinstance(uuid.UUID(flow_run_id), uuid.UUID)

    async def test_runners_deployment_run_route_execs_flow_run(self, runner: Runner):
        mock_flow_run_id = str(uuid.uuid4())

        mock_client = mock.create_autospec(PrefectClient, spec_set=True)
        mock_client.create_flow_run_from_deployment.return_value.id = mock_flow_run_id
        mock_get_client = mock.create_autospec(get_client, spec_set=True)
        mock_get_client.return_value.__aenter__.return_value = mock_client
        mock_get_client.return_value.__aexit__.return_value = None

        async with runner:
            deployment_id = await create_deployment(runner, simple_flow)
            webserver = await build_server(runner)
            client = TestClient(webserver)

            with (
                mock.patch("prefect.runner.server.get_client", new=mock_get_client),
                mock.patch.object(runner, "execute_in_background"),
            ):
                with client:
                    response = client.post(f"/deployment/{deployment_id}/run")
                assert response.status_code == 201, response.json()
                flow_run_id = response.json()["flow_run_id"]
                assert flow_run_id == mock_flow_run_id
                assert isinstance(uuid.UUID(flow_run_id), uuid.UUID)
                mock_client.create_flow_run_from_deployment.assert_called_once_with(
                    deployment_id=uuid.UUID(deployment_id), parameters={}
                )


class TestWebserverFlowRoutes:
    async def test_flow_router_runs_managed_flow(self, runner: Runner):
        async with runner:
            await create_deployment(runner, simple_flow)
            webserver = await build_server(runner)
            client = TestClient(webserver)

            with mock.patch.object(
                runner, "execute_flow_run", new_callable=mock.AsyncMock
            ) as mock_run:
                response = client.post(
                    "/flow/run",
                    json={"entrypoint": f"{__file__}:simple_flow", "parameters": {}},
                )
                assert response.status_code == 201, response.status_code
                assert isinstance(FlowRun.model_validate(response.json()), FlowRun)
                mock_run.assert_called()

    @pytest.mark.parametrize("flow_name", ["a_missing_flow"])
    @pytest.mark.parametrize(
        "flow_file", [__file__, "/not/a/path.py", "not/a/python/file.txt"]
    )
    async def test_missing_flow_raises_a_404(
        self,
        runner: Runner,
        flow_file: str,
        flow_name: str,
    ):
        async with runner:
            await create_deployment(runner, simple_flow)
            webserver = await build_server(runner)
        client = TestClient(webserver)

        response = client.post(
            "/flow/run",
            json={"entrypoint": f"{flow_file}:{flow_name}", "parameters": {}},
        )
        assert response.status_code == 404, response.status_code

    @mock.patch("prefect.runner.server.load_flow_from_entrypoint")
    async def test_flow_router_complains_about_running_unmanaged_flow(
        self, mocked_load: mock.MagicMock, runner: Runner, caplog
    ):
        async with runner:
            await create_deployment(runner, simple_flow)
            webserver = await build_server(runner)
            client = TestClient(webserver)

            @flow
            def new_flow():
                pass

            # force load_flow_from_entrypoint to return a different flow
            mocked_load.return_value = new_flow
            with mock.patch.object(
                runner, "execute_flow_run", new_callable=mock.AsyncMock
            ) as mock_run:
                response = client.post(
                    "/flow/run", json={"entrypoint": "doesnt_matter", "parameters": {}}
                )
                # the flow should still be run even though it's not managed
                assert response.status_code == 201, response.status_code
                assert isinstance(FlowRun.model_validate(response.json()), FlowRun)
                mock_run.assert_called()

            # we should have logged a warning
            assert (
                "Flow new-flow is not directly managed by the runner. Please "
                "include it in the runner's served flows' import namespace."
                in caplog.text
            )

    @mock.patch("prefect.runner.server.load_flow_from_entrypoint")
    async def test_flow_router_complains_about_flow_with_different_schema(
        self, mocked_load: mock.MagicMock, runner: Runner, caplog
    ):
        async with runner:
            await create_deployment(runner, simple_flow)
            webserver = await build_server(runner)
            client = TestClient(webserver)

            @flow
            def simple_flow2(age: int = 99):
                pass

            # force load_flow_from_entrypoint to return the updated flow
            simple_flow2.name = "simple_flow"
            mocked_load.return_value = simple_flow2
            with mock.patch.object(
                runner, "execute_flow_run", new_callable=mock.AsyncMock
            ) as mock_run:
                response = client.post(
                    "/flow/run", json={"entrypoint": "doesnt_matter", "parameters": {}}
                )
                # we'll still attempt to run the changed flow
                assert response.status_code == 201, response.status_code
                assert isinstance(FlowRun.model_validate(response.json()), FlowRun)
                mock_run.assert_called()

            # we should have logged a warning
            assert (
                "A change in flow parameters has been detected. Please restart the runner."
                in caplog.text
            )
