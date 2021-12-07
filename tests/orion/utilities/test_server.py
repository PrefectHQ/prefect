import anyio
import httpx
import pytest
from fastapi import Depends, FastAPI, Request, status, Path
from fastapi.testclient import TestClient

from prefect.orion.utilities.server import (
    OrionRouter,
    response_scoped_dependency,
)


def test_response_scoped_dependency_is_resolved():
    @response_scoped_dependency
    async def test():
        yield "test"

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(test=Depends(test)):
        return test

    app.include_router(router)

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "test"


def test_response_scoped_dependency_can_have_dependencies():
    async def bar():
        return "bar"

    @response_scoped_dependency
    async def test(bar=Depends(bar)):
        yield "test", bar

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(test=Depends(test)):
        return test

    app.include_router(router)

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == ["test", "bar"]


def test_response_scoped_dependency_can_have_request_dependency():
    @response_scoped_dependency
    async def test(request: Request):
        yield request.path_params

    app = FastAPI(name="test")
    router = OrionRouter()

    @router.get("/{param}")
    async def read_flow_run(param: str = Path(...), test=Depends(test)):
        return test

    app.include_router(router)

    client = TestClient(app)
    response = client.get("/foo")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"param": "foo"}


async def test_response_scoped_dependency_is_closed_before_request_scoped():
    # This test is not a strict guarantee that the behavior is correct, but if you
    # change the OrionAPIRoute class to use the FastAPI stack instead of the correctly
    # scoped stack, the test will fail which indicates it is a helpful signal.
    order = []

    @response_scoped_dependency
    async def response_scoped():
        yield
        await anyio.sleep(0.5)
        order.append("response")

    def make_request_scoped():
        # Use a factory to avoid caching
        async def request_scoped():
            yield
            order.append("request")

        return request_scoped

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(
        x=Depends(make_request_scoped()),
        y=Depends(response_scoped),
        z=Depends(make_request_scoped()),
    ):
        order.append("endpoint")

    app.include_router(router)

    async with httpx.AsyncClient(app=app) as client:
        response = await client.get("http://localhost/")

    assert response.status_code == status.HTTP_200_OK
    assert order == ["endpoint", "response", "request", "request"]


def test_response_scoped_dependency_is_overridable():
    @response_scoped_dependency
    async def test():
        yield "test"

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(test=Depends(test)):
        return test

    def override():
        yield "override"

    app.include_router(router)
    app.dependency_overrides[test] = override

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == "override"
