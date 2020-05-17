# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


"""
Tests that the GraphQL server class behaves in an expected manner, especially with regard to errors.
"""
from typing import Any

import ariadne
import httpx
import json
import pytest
import uuid
from ariadne import make_executable_schema
from ariadne.asgi import GraphQL
from graphql import GraphQLResolveInfo
from starlette.applications import Starlette

import prefect_server
from prefect_server import api
from prefect_server.utilities import context
from prefect_server.utilities.exceptions import Unauthenticated, Unauthorized


class TestDummyClient:
    @pytest.fixture(autouse=True)
    async def dummy_client(self,):
        """
        Client for a dummy server
        """
        type_defs = ariadne.gql(
            """
            scalar JSON

            type Query {
                headers: JSON
                hello: String
                value_error_required: String!
                value_error: String
                type_error: String
                unauthenticated_error: String
                unauthorized_error: String
            }

            """
        )
        query = ariadne.QueryType()

        @query.field("hello")
        def hello(parent: Any, info: GraphQLResolveInfo):
            return "👋"

        @query.field("value_error")
        @query.field("value_error_required")
        def value_error(parent: Any, info: GraphQLResolveInfo):
            raise ValueError("this is a value error")

        @query.field("type_error")
        def type_error(parent: Any, info: GraphQLResolveInfo):
            raise TypeError("this is a type error")

        @query.field("unauthenticated_error")
        def unauthenticated_error(parent: Any, info: GraphQLResolveInfo):
            raise Unauthenticated("this is an unauthenticated error")

        @query.field("unauthorized_error")
        def unauthorized_error(parent: Any, info: GraphQLResolveInfo):
            raise Unauthorized("this is an unauthorized error")

        schema = make_executable_schema(type_defs, query)
        app = Starlette()
        app.mount("/", GraphQL(schema))
        async with httpx.Client(app=app, base_url="http://prefect.io") as dummy_client:
            yield dummy_client

    @pytest.fixture
    def run_dummy_query(self, dummy_client):
        async def run_dummy_query(query, headers=None):
            headers = headers or {}
            return await dummy_client.post(
                prefect_server.config.services.graphql.path,
                json=dict(query=query),
                headers=headers,
            )

        return run_dummy_query

    async def test_error_parsing_query_is_400(self, run_dummy_query):
        response = await run_dummy_query("""query { hi }""")
        assert response.status_code == 400
        assert "Cannot query field" in response.json()["errors"][0]["message"]

    async def test_hello(self, run_dummy_query):
        response = await run_dummy_query(
            """
            query {
                hello
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"]["hello"] == "👋"
        assert "errors" not in result

    async def test_mix_error_and_data(self, run_dummy_query):
        response = await run_dummy_query(
            """
            query {
                hello
                value_error
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"]["hello"] == "👋"
        assert "this is a value error" in result["errors"][0]["message"]

    async def test_mix_error_and_data_when_error_is_required_has_no_data(
        self, run_dummy_query
    ):
        response = await run_dummy_query(
            """
            query {
                hello
                value_error_required
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"] is None
        assert "this is a value error" in result["errors"][0]["message"]

    async def test_type_error(self, run_dummy_query):
        response = await run_dummy_query(
            """
            query {
                type_error
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"]["type_error"] is None
        assert "this is a type error" in result["errors"][0]["message"]

    async def test_value_error(self, run_dummy_query):
        response = await run_dummy_query(
            """
            query {
                value_error
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"]["value_error"] is None
        assert "this is a value error" in result["errors"][0]["message"]

    async def test_unauthenticated_error(self, run_dummy_query):
        response = await run_dummy_query(
            """
            query {
                unauthenticated_error
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"]["unauthenticated_error"] is None
        assert "this is an unauthenticated error" in result["errors"][0]["message"]

    async def test_unauthorized_error(self, run_dummy_query):
        response = await run_dummy_query(
            """
            query {
                unauthorized_error
            }
            """,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["data"]["unauthorized_error"] is None
        assert "this is an unauthorized error" in result["errors"][0]["message"]
