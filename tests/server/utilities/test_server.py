import urllib.parse

import pytest
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
)
from fastapi.testclient import TestClient

from prefect.server.utilities.server import PrefectRouter


def test_request_scoped_dependency_cannot_raise_after_yield():
    # Converse to the above test. This does not cover any of our code, just FastAPI
    # behavior.
    async def test():
        yield
        raise HTTPException(status_code=202)

    app = FastAPI()
    router = PrefectRouter()

    @router.get("/")
    def foo(
        x=Depends(test),
    ):
        pass

    app.include_router(router)

    client = TestClient(app)

    # In newer FastAPI versions, FastAPI raises a runtime error complaining about
    # an exception during the response
    expected_type = RuntimeError
    match = "Caught handled exception, but response already started"

    with pytest.raises(expected_type, match=match):
        client.get("/")


class TestParsing:
    @pytest.fixture
    def client(self):
        app = FastAPI()
        router = PrefectRouter()

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
