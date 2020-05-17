# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import json
import uuid
from typing import Any

import ariadne
import graphql
import pendulum
import pytest
from graphql import GraphQLResolveInfo

from prefect_server.graphql import scalars


class FakeASTNode:
    def __init__(self, value):
        self.value = value


type_defs = ariadne.gql(
    """
    scalar JSON
    scalar DateTime
    scalar UUID

    type Query {
        json_input(json: JSON!): Int!
        json_output: JSON!

        datetime_input(dt: DateTime): Int!
        datetime_output: DateTime!

        uuid_input(uuid: UUID): String!
        uuid_output: UUID!
    }
    """
)

query = ariadne.QueryType()


@query.field("json_input")
def json_input_resolver(parent: Any, info: GraphQLResolveInfo, json):
    return json["x"]


@query.field("json_output")
def json_output_resolver(parent: Any, info: GraphQLResolveInfo):
    return {"x": [1, 2]}


@query.field("datetime_input")
def datetime_input_resolver(parent: Any, info: GraphQLResolveInfo, dt):
    return dt.year


@query.field("datetime_output")
def datetime_output_resolver(parent: Any, info: GraphQLResolveInfo):
    return pendulum.datetime(2020, 1, 1, 1, tz="EST")


@query.field("uuid_input")
def uuid_input_resolver(parent: Any, info: GraphQLResolveInfo, uuid):
    return uuid


@query.field("uuid_output")
def uuid_output_resolver(parent: Any, info: GraphQLResolveInfo):
    return "8c9c95c5-30b8-467b-8acb-384c86dc3ab8"


schema = ariadne.make_executable_schema([type_defs], query, *scalars.resolvers)


class TestJSONScalar:
    @pytest.mark.parametrize("x", [1.0, "2", [3, {"4": 5}]])
    async def test_json_scalar_serialize_leaves_value_unchanged(self, x):
        assert scalars.json_serializer(x) is x

    @pytest.mark.parametrize("x", [1.0, "2", [3, {"4": 5}]])
    async def test_json_scalar_value_parser_leaves_value_unchanged(self, x):
        assert scalars.json_value_parser(x) is x

    @pytest.mark.parametrize("x", [1.0, "2", [3, {"4": 5}]])
    async def test_json_scalar_literal_parser_loads_json_from_string(self, x):

        assert scalars.json_literal_parser(FakeASTNode(json.dumps(x))) == x


class TestJSONScalarGraphQL:
    async def test_json_scalar_as_output(self):
        query = "query { json_output }"
        result = graphql.execute(schema, graphql.parse(query))
        assert result.data["json_output"] == {"x": [1, 2]}

    async def test_json_scalar_input_as_query_string(self):
        """
        Won't work unless the literal JSON string is parsed as JSON and passed to the resolver,
        so it can be indexed
        """
        query = r"""
            query {
                json_input(json: "{\"x\": 1}")
            }
            """
        result = graphql.execute(schema, graphql.parse(query))
        assert result.data["json_input"] == 1

    async def test_json_scalar_input_as_variable(self):
        query = r"""
            query($j: JSON) {
                json_input(json: $j)
            }
            """
        result = graphql.execute(
            schema, graphql.parse(query), variable_values=dict(j={"x": 1})
        )
        assert result.data["json_input"] == 1


class TestDateTimeScalar:
    async def test_datetime_scalar_serialize_creates_string(self):
        dt = pendulum.now()
        assert scalars.datetime_serializer(dt) == dt.isoformat()

    async def test_datetime_scalar_value_parser_loads_dt_from_string(self):
        dt = pendulum.now()
        assert scalars.datetime_value_parser(dt.isoformat()) == dt

    async def test_datetime_scalar_literal_parser_loads_json_from_string(self):
        dt = pendulum.now()
        assert scalars.datetime_literal_parser(FakeASTNode(dt.isoformat())) == dt


class TestDateTimeScalarGraphQL:
    async def test_datetime_scalar_as_output(self):
        query = "query { datetime_output }"
        result = graphql.execute(schema, graphql.parse(query))
        assert (
            result.data["datetime_output"]
            == pendulum.datetime(2020, 1, 1, 1, tz="EST").isoformat()
        )

    async def test_datetime_scalar_input_as_query_string(self):
        query = """
            query {
                datetime_input(dt: "2018-01-01T01:00:00-05:00")
            }
            """
        result = graphql.execute(schema, graphql.parse(query))
        assert result.data["datetime_input"] == 2018

    async def test_datetime_scalar_input_as_variable(self):
        query = r"""
            query($dt: DateTime) {
                datetime_input(dt: $dt)
            }
            """
        result = graphql.execute(
            schema,
            graphql.parse(query),
            variable_values=dict(
                dt=pendulum.datetime(2018, 1, 1, 1, tz="EST").isoformat()
            ),
        )
        assert result.data["datetime_input"] == 2018


class TestUUIDScalar:
    async def test_uuid_scalar_serialize_is_pass_through(self):
        id = str(uuid.uuid4())
        assert scalars.uuid_serializer(id) == id

    async def test_uuid_scalar_serialize_converts_to_string(self):
        id = uuid.uuid4()
        assert scalars.uuid_serializer(id) == str(id)

    async def test_uuid_scalar_value_parser_passes_through(self):
        id = str(uuid.uuid4())
        assert scalars.uuid_value_parser(id) == id

    async def test_uuid_scalar_value_parser_validates_uuid(self):
        with pytest.raises(ValueError):
            scalars.uuid_value_parser("x")

    async def test_uuid_scalar_literal_parser_passes_through(self):
        id = str(uuid.uuid4())
        assert scalars.uuid_literal_parser(FakeASTNode(id)) == id

    async def test_uuid_scalar_literal_parser_validates_uuid(self):
        with pytest.raises(ValueError):
            scalars.uuid_literal_parser(FakeASTNode("x"))


class TestUUIDScalarGraphQL:
    async def test_uuid_scalar_output(self):
        query = "query { uuid_output }"
        result = graphql.execute(schema, graphql.parse(query))
        assert result.data["uuid_output"] == "8c9c95c5-30b8-467b-8acb-384c86dc3ab8"

    async def test_uuid_scalar_input_as_query_string(self):
        query = """
            query {
                uuid_input(uuid: "8c9c95c5-30b8-467b-8acb-384c86dc3ab8")
            }
            """
        result = graphql.execute(schema, graphql.parse(query))
        assert result.data["uuid_input"] == "8c9c95c5-30b8-467b-8acb-384c86dc3ab8"

    async def test_uuid_scalar_input_as_query_string_validates(self):
        query = """
            query {
                uuid_input(uuid: "hello")
            }
            """
        result = graphql.execute(schema, graphql.parse(query))
        assert "invalid value" in str(result.errors)

    async def test_uuid_scalar_input_as_variable(self):
        query = """
            query($uuid: UUID) {
                uuid_input(uuid: $uuid)
            }
            """
        result = graphql.execute(
            schema,
            graphql.parse(query),
            variable_values=dict(uuid="8c9c95c5-30b8-467b-8acb-384c86dc3ab8"),
        )
        assert result.data["uuid_input"] == "8c9c95c5-30b8-467b-8acb-384c86dc3ab8"

    async def test_uuid_scalar_input_as_variable_validates(self):
        query = """
            query($uuid: UUID) {
                uuid_input(uuid: $uuid)
            }
            """
        result = graphql.execute(
            schema, graphql.parse(query), variable_values=dict(uuid="hello")
        )
        assert "invalid value" in str(result.errors)

    async def test_uuid_scalar_input_as_variable_validates_object(self):
        query = """
            query($uuid: UUID) {
                uuid_input(uuid: $uuid)
            }
            """
        result = graphql.execute(
            schema, graphql.parse(query), variable_values=dict(uuid=dict(a=1))
        )
        assert "invalid value" in str(result.errors)
        assert "Could not parse UUID" in str(result.errors)
