import urllib.parse

import anyio
import fastapi
import httpx
import packaging.version
import pytest
from fastapi import Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.testclient import TestClient

from prefect.orion.utilities.server import OrionRouter, response_scoped_dependency


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


async def test_response_scoped_dependency_is_closed_before_response_is_returned():
    order = []

    @response_scoped_dependency
    async def response_scoped():
        order.append("response enter")
        yield
        order.append("response exit")

    async def request_scoped():
        order.append("request enter")
        yield
        order.append("request exit")

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(
        x=Depends(request_scoped),
        y=Depends(response_scoped),
    ):
        order.append("endpoint called")

    app.include_router(router)

    async with httpx.AsyncClient(app=app) as client:
        order.append("request sent")
        response = await client.get("http://localhost/")
        order.append("response received")

    assert response.status_code == status.HTTP_200_OK
    assert order == [
        "request sent",
        "request enter",
        "response enter",
        "endpoint called",
        "response exit",
        # We would like to demonstrate that the response can be received before the
        # request exits, but inserting a sleep into shutdown of the request context
        # does not change this ordering. We've seen the response return before the
        # request context exits when using a non-ephemeral server.
        "request exit",
        "response received",
    ]


def test_response_scoped_dependency_can_raise_after_yield():
    # Unlike normal dependencies, response scoped dependencies can raise the exceptions
    # after yielding to set the response
    # https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception

    @response_scoped_dependency
    async def test():
        yield
        raise HTTPException(status_code=202)

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(
        x=Depends(test),
    ):
        pass

    app.include_router(router)

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 202


def test_request_scoped_dependency_cannot_raise_after_yield():
    # Converse to the above test. This does not cover any of our code, just FastAPI
    # behavior.
    async def test():
        yield
        raise HTTPException(status_code=202)

    app = FastAPI()
    router = OrionRouter()

    @router.get("/")
    def foo(
        x=Depends(test),
    ):
        pass

    app.include_router(router)

    client = TestClient(app)
    if packaging.version.parse(fastapi.__version__) < packaging.version.parse("0.74.0"):
        # The exception is raised in the app (and consequently here) instead of in
        # the response
        expected_type = HTTPException
        match = ".*"
    else:
        # In newer FastAPI versions, FastAPI raises a runtime error complaining about
        # an exception during the response
        expected_type = RuntimeError
        match = "Caught handled exception, but response already started"

    with pytest.raises(expected_type, match=match):
        client.get("/")


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


class TestParsing:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        router = OrionRouter()

        @router.get("/{x}")
        def echo(x: str):
            return x

        app.include_router(router)
        client = TestClient(app)
        return client

    def test_url_encoded_variables(self, client):
        """FastAPI automatically handles url-encoded variables"""
        x = "| ; 👍"
        response = client.get(f"/{x}")
        quoted_response = client.get(urllib.parse.quote(f"/{x}"))

        assert x == response.json() == quoted_response.json()
