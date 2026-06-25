import urllib.parse

import pytest
from fastapi import (
    FastAPI,
)
from fastapi.testclient import TestClient

from prefect.server.utilities.server import PrefectRouter, method_paths_from_routes

pytestmark = pytest.mark.clear_db


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


def test_method_paths_from_routes_includes_effective_included_router_paths() -> None:
    app = FastAPI()
    router = PrefectRouter()

    @router.get("/items/{name}")
    def read_item(name: str) -> str:
        return name

    app.include_router(router, prefix="/api")

    assert "GET /api/items/{name}" in method_paths_from_routes(app.router.routes)
