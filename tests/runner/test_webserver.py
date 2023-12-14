import uuid
from typing import Callable, List
from unittest import mock

import pydantic
import pytest
from prefect._vendor.fastapi.testclient import TestClient

from prefect import flow
from prefect.runner import Runner
from prefect.runner.server import build_server
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS,
    PREFECT_RUNNER_SERVER_HOST,
    PREFECT_RUNNER_SERVER_PORT,
    temporary_settings,
)


@pytest.fixture(autouse=True)
def tmp_runner_settings():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: True,
            PREFECT_RUNNER_SERVER_HOST: "0.0.0.0",
            PREFECT_RUNNER_SERVER_PORT: 0,
        }
    ):
        yield


@pytest.fixture(scope="function")
async def runner(tmp_runner_settings) -> Runner:
    return Runner()


async def create_deployment(runner: Runner, func: Callable):
    # Use unique names to force multiple deployments to be created
    deployment_id = await runner.add_flow(
        func, f"{uuid.uuid4()}", enforce_parameter_schema=True
    )
    return str(deployment_id)


async def test_deployment_router_not_added_if_experimental_flag_is_false(
    runner: Runner,
):
    with temporary_settings(
        updates={PREFECT_EXPERIMENTAL_ENABLE_EXTRA_RUNNER_ENDPOINTS: False}
    ):
        webserver = await build_server(runner)
        deployment_routes = [
            r
            for r in webserver.routes
            if r.path.startswith("/deployment") and r.path.endswith("/run")
        ]
        assert len(deployment_routes) == 0


async def test_runners_deployment_run_routes_exist(runner: Runner):
    @flow(version="test")
    def f(verb: str = "party"):
        print(f"I'm just here to {verb}")

    deployment_ids = [await create_deployment(runner, f) for _ in range(3)]
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


async def test_runners_deployment_run_route_does_input_validation(runner: Runner):
    @flow(version="test")
    def f(verb: str = "party"):
        print(f"I'm just here to {verb}")

    deployment_id = await create_deployment(runner, f)
    webserver = await build_server(runner)

    client = TestClient(webserver)
    response = client.post(f"/deployment/{deployment_id}/run", json={"verb": False})
    assert response.status_code == 400

    response = client.post(f"/deployment/{deployment_id}/run", json={"verb": "clobber"})
    assert response.status_code == 201
    flow_run_id = response.json()["flow_run_id"]
    assert isinstance(uuid.UUID(flow_run_id), uuid.UUID)


async def test_runners_deployment_run_route_with_complex_args(runner: Runner):
    class A(pydantic.BaseModel):
        a: int = 0

    class B(pydantic.BaseModel):
        a: A = A()
        b: bool = False

    @flow
    def complex_flow(
        x: int, y: str = "hello", z: List[bool] = [True], a: A = A(), b: B = B()
    ):
        print(x, y, z, a, b)

    deployment_id = await runner.add_flow(
        complex_flow, f"{uuid.uuid4()}", enforce_parameter_schema=True
    )
    webserver = await build_server(runner)
    client = TestClient(webserver)
    response = client.post(f"/deployment/{deployment_id}/run", json={"x": 100})
    assert response.status_code == 201, response.json()
    flow_run_id = response.json()["flow_run_id"]
    assert isinstance(uuid.UUID(flow_run_id), uuid.UUID)


@mock.patch("prefect.runner.server.get_client")
async def test_runners_deployment_run_route_execs_flow_run(
    mock_get_client: mock.Mock, runner: Runner
):
    @flow(version="test")
    def f(verb: str = "party"):
        print(f"I'm just here to {verb}")

    mock_flow_run_id = str(uuid.uuid4())
    mock_client = mock.AsyncMock()
    mock_get_client.return_value.__aenter__.return_value = mock_client
    mock_client.create_flow_run_from_deployment.return_value.id = mock_flow_run_id

    deployment_id = await create_deployment(runner, f)
    webserver = await build_server(runner)

    client = TestClient(webserver)
    response = client.post(f"/deployment/{deployment_id}/run")

    assert response.status_code == 201, response.json()
    flow_run_id = response.json()["flow_run_id"]
    assert flow_run_id == mock_flow_run_id
    assert isinstance(uuid.UUID(flow_run_id), uuid.UUID)

    mock_client.create_flow_run_from_deployment.assert_called_once_with(
        deployment_id=uuid.UUID(deployment_id), parameters={}
    )
