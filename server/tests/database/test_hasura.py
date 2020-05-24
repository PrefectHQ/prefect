# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


from textwrap import dedent
from unittest.mock import MagicMock

import pendulum
import pytest
from asynctest import CoroutineMock
from box import Box
from graphql.error import GraphQLSyntaxError

import prefect_server
from prefect.utilities.graphql import EnumValue, parse_graphql, parse_graphql_arguments
from prefect_server.database.hasura import HasuraClient, Variable
from prefect_server.utilities import context, exceptions
from prefect_server.utilities.tests import set_temporary_config


hasura = HasuraClient()


class TestExecute:
    @pytest.fixture(autouse=True)
    async def monkeypatch_post_query_variables(self, monkeypatch):
        """
        Patches request.post so that hasura.execute() returns a Box containing the
        GraphQL query and variables.
        """
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=Box(
                            query=kwargs["json"]["query"],
                            variables=kwargs["json"]["variables"],
                        )
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)

    async def test_execute_accepts_gql(self):
        result = await hasura.execute("query { flow { id } }")
        assert result.data.query == "query { flow { id } }"

    async def test_execute_accepts_objects_and_parses(self):
        result = await hasura.execute({"query": {"flow": {"id"}}})
        expected_query = dedent(
            """
            query {
                flow {
                    id
                }
            }
            """
        ).strip()
        assert result.data.query == expected_query

    async def test_execute_accepts_variables_and_parses(self):
        result = await hasura.execute(
            "query { hello }", variables=dict(x=1, y=dict(z=2))
        )
        assert result.data.variables == dict(x=1, y=dict(z=2))

    async def test_query_is_valid(self):
        with pytest.raises(GraphQLSyntaxError):
            await hasura.execute("query { invalid {} }")

    async def test_handle_uniqueness_violations(self, monkeypatch):
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=Box(
                            query=kwargs["json"]["query"],
                            variables=kwargs["json"]["variables"],
                        ),
                        errors=[Box(message="Uniqueness violation.")],
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)
        with pytest.raises(ValueError, match="Uniqueness violation"):
            await hasura.execute("query { hello }", variables=dict(x=1, y=dict(z=2)))

    async def test_handle_foreign_key_violations(self, monkeypatch):
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=Box(
                            query=kwargs["json"]["query"],
                            variables=kwargs["json"]["variables"],
                        ),
                        errors=[Box(message="Foreign key violation.")],
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)
        with pytest.raises(ValueError, match="Foreign key violation"):
            await hasura.execute("query { hello }", variables=dict(x=1, y=dict(z=2)))

    async def test_handle_check_constraint_violations(self, monkeypatch):
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=Box(
                            query=kwargs["json"]["query"],
                            variables=kwargs["json"]["variables"],
                        ),
                        errors=[Box(message="Check constraint violation")],
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)
        with pytest.raises(exceptions.Unauthorized):
            await hasura.execute("query { hello }", variables=dict(x=1, y=dict(z=2)))

    async def test_handle_connection_error(self, monkeypatch):
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=Box(
                            query=kwargs["json"]["query"],
                            variables=kwargs["json"]["variables"],
                        ),
                        errors=[Box(message="connection error")],
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)
        start_time = pendulum.now("utc")
        with set_temporary_config("hasura.execute_retry_seconds", 3):
            with pytest.raises(ValueError, match="Unable to connect to postgres"):
                await hasura.execute(
                    "query { hello }", variables=dict(x=1, y=dict(z=2))
                )
        # confirm we waited while retrying, leaving a couple of seconds to be conservative
        assert pendulum.now("utc") > start_time.add(seconds=2)


class TestGenerateInsertGraphQL:
    async def test_generate_gql_insert_flows(self):
        graphql = await hasura.insert("flow", objects=[], run_mutation=False)
        expected_query = """
            insert: insert_flow(objects: $insert_objects) {
                affected_rows
            }
        """
        expected_defs = "$insert_objects: [flow_insert_input!]!"
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="insert_objects", type="[flow_insert_input!]!", value=[])
        ]

    async def test_generate_selection_set(self):
        graphql = await hasura.insert(
            "flow", objects=[], selection_set="affected_rows", run_mutation=False
        )
        expected_query = """
            insert: insert_flow(objects: $insert_objects) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()

    async def test_generate_selection_set_returning(self):
        graphql = await hasura.insert(
            "flow", objects=[], selection_set={"returning": {"id"}}, run_mutation=False,
        )
        expected_query = """
            insert: insert_flow(objects: $insert_objects) {
                returning {
                    id
                }
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()

    async def test_generate_objects(self):
        graphql = await hasura.insert(
            "flow",
            objects=[{"a": 1, "b": {"c": "2"}}],
            selection_set={"returning": {"id"}},
            run_mutation=False,
        )
        expected_query = """
            insert: insert_flow(objects: $insert_objects) {
                returning {
                    id
                }
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(
                name="insert_objects",
                type="[flow_insert_input!]!",
                value=[{"a": 1, "b": {"c": "2"}}],
            )
        ]

    async def test_generate_multiple_objects(self):
        graphql = await hasura.insert(
            "flow",
            objects=[{"a": 1}, {"b": "2"}],
            selection_set={"returning": {"id"}},
            run_mutation=False,
        )
        expected_query = """
            insert: insert_flow(objects: $insert_objects) {
                returning {
                    id
                }
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(
                name="insert_objects",
                type="[flow_insert_input!]!",
                value=[{"a": 1}, {"b": "2"}],
            )
        ]

    async def test_on_conflict(self):
        graphql = await hasura.insert(
            "flow", objects=[], on_conflict={"constraint": "pk1"}, run_mutation=False
        )
        expected_query = """
            insert: insert_flow(objects: $insert_objects, on_conflict: $insert_on_conflict) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="insert_objects", type="[flow_insert_input!]!", value=[]),
            Variable(
                name="insert_on_conflict",
                type="flow_on_conflict",
                value={"constraint": "pk1"},
            ),
        ]

    async def test_on_conflict_string(self):
        graphql = await hasura.insert(
            "flow", objects=[], on_conflict="{ constraint: pk1 }", run_mutation=False
        )
        expected_query = """
            insert: insert_flow(objects: $insert_objects, on_conflict: { constraint: pk1 }) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()

    async def test_alias(self):
        graphql = await hasura.insert("flow", objects=[], alias="x", run_mutation=False)
        expected_query = """
            x: insert_flow(objects: $x_objects) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="x_objects", type="[flow_insert_input!]!", value=[])
        ]


class TestInsert:
    @pytest.fixture(autouse=True)
    async def monkeypatch_post_query_variables(self, monkeypatch):
        """
        Patches request.post so that await hasura.execute() returns a Box containing the
        GraphQL query and variables.
        """
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=dict(
                            insert=Box(
                                query=kwargs["json"]["query"],
                                variables=kwargs["json"]["variables"],
                            )
                        )
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)

    @pytest.mark.parametrize("objects", [[1], (1,), {1}])
    async def test_objects_must_be_collection(self, objects):
        assert await hasura.insert("flow", objects)

    @pytest.mark.parametrize("objects", [{"x": 1}, 1, "x"])
    async def test_raise_if_objects_are_not_collection(self, objects):
        with pytest.raises(TypeError) as exc:
            await hasura.insert("flow", objects)
        assert "`objects` should be a collection" in str(exc.value)

    async def test_on_conflict_kwargs(self):
        assert await hasura.insert(
            "flow", objects=[], on_conflict={"constraint": EnumValue("pk1")}
        )

    async def test_generate_mutation(self):
        result = await hasura.insert("flow", objects=[{"name": "test"}])
        expected_query = dedent(
            """
            mutation($insert_objects: [flow_insert_input!]!) {
                insert: insert_flow(objects: $insert_objects) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(insert_objects=[{"name": "test"}])

    async def test_generate_mutation_selection_set(self):
        result = await hasura.insert(
            "flow",
            objects=[{"name": "test"}],
            selection_set={"returning": ["id", "name"]},
        )
        expected_query = dedent(
            """
            mutation($insert_objects: [flow_insert_input!]!) {
                insert: insert_flow(objects: $insert_objects) {
                    returning {
                        id
                        name
                    }
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(insert_objects=[{"name": "test"}])


class TestGenerateDeleteGraphQL:
    async def test_generate_gql_delete_flows(self):
        graphql = await hasura.delete("flow", where={}, run_mutation=False)
        expected_query = """
            delete: delete_flow(where: $delete_where) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="delete_where", type="flow_bool_exp!", value={})
        ]

    async def test_generate_gql_delete_flows_selection_set(self):
        graphql = await hasura.delete(
            "flow", where={}, selection_set={"returning": {"id"}}, run_mutation=False
        )
        expected_query = """
            delete: delete_flow(where: $delete_where) {
                returning {
                    id
                }
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()

    async def test_generate_gql_delete_flows_with_where(self):
        where = {"name": {"_eq": "x"}}
        graphql = await hasura.delete("flow", where=where, run_mutation=False)
        assert graphql["variables"] == [
            Variable(
                name="delete_where",
                type="flow_bool_exp!",
                value={"name": {"_eq": "x"}},
            )
        ]

    async def test_generate_gql_delete_flows_with_complex_where(self):
        where = {"_or": {"name": {"_eq": "x"}, "slug": {"_eq": "x"}}}
        graphql = await hasura.delete("flow", where=where, run_mutation=False)
        assert graphql["variables"] == [
            Variable(name="delete_where", type="flow_bool_exp!", value=where)
        ]

    async def test_alias(self):
        graphql = await hasura.delete("flow", where={}, alias="x", run_mutation=False)
        expected_query = """
            x: delete_flow(where: $x_where) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="x_where", type="flow_bool_exp!", value={})
        ]


class TestDelete:
    @pytest.fixture(autouse=True)
    async def monkeypatch_post_query_variables(self, monkeypatch):
        """
        Patches request.post so that await hasura.execute() returns a Box containing the
        GraphQL query and variables.
        """
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=dict(
                            delete=Box(
                                query=kwargs["json"]["query"],
                                variables=kwargs["json"]["variables"],
                            )
                        )
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)

    async def test_where_is_a_dict(self):
        assert await hasura.delete("flow", where={"x": 1})

    async def test_where_must_be_provided(self):
        with pytest.raises(TypeError) as exc:
            await hasura.delete("flow")
        assert "`where` must be provided" in str(exc.value)

    async def test_where_can_be_none_if_id_is_provided(self):
        assert await hasura.delete("flow", id=1)

    async def test_where_must_be_dict(self):
        with pytest.raises(TypeError) as exc:
            await hasura.delete("flow", where=1)
        assert "must be provided" in str(exc.value)

    async def test_generate_mutation(self):
        result = await hasura.delete("flow", where={"color": "red"})
        expected_query = dedent(
            """
            mutation($delete_where: flow_bool_exp!) {
                delete: delete_flow(where: $delete_where) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(delete_where={"color": "red"})

    async def test_generate_mutation_selection_set(self):
        result = await hasura.delete(
            "flow", where={"color": "red"}, selection_set={"returning": ["id", "name"]},
        )
        expected_query = dedent(
            """
            mutation($delete_where: flow_bool_exp!) {
                delete: delete_flow(where: $delete_where) {
                    returning {
                        id
                        name
                    }
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(delete_where={"color": "red"})

    async def test_id_creates_where(self):
        result = await hasura.delete("flow", id="1")
        expected_query = dedent(
            """
            mutation($delete_where: flow_bool_exp!) {
                delete: delete_flow(where: $delete_where) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(delete_where={"id": {"_eq": "1"}})


class TestGenerateUpdateGraphQL:
    async def test_generate_gql_update_flows_set(self):
        graphql = await hasura.update(
            "flow", where={}, set={"name": "x"}, run_mutation=False
        )
        expected_query = """
            update: update_flow(where: $update_where, _set: $update_set) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="update_where", type="flow_bool_exp!", value={}),
            Variable(name="update_set", type="flow_set_input", value={"name": "x"}),
        ]

    async def test_generate_gql_update_flows_selection_set(self):
        graphql = await hasura.update(
            "flow",
            where={},
            set={"name": "x"},
            selection_set={"returning": {"id"}},
            run_mutation=False,
        )
        expected_query = """
            update: update_flow(where: $update_where, _set: $update_set) {
                returning {
                    id
                }
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()

    async def test_generate_gql_update_flows_with_where(self):
        graphql = await hasura.update(
            "flow", where={"name": {"_eq": "x"}}, set={"name": "y"}, run_mutation=False,
        )
        assert graphql["variables"] == [
            Variable(
                name="update_where",
                type="flow_bool_exp!",
                value={"name": {"_eq": "x"}},
            ),
            Variable(name="update_set", type="flow_set_input", value={"name": "y"}),
        ]

    async def test_generate_gql_update_flows_with_complex_where(self):
        where = {"_or": {"name": {"_eq": "x"}, "slug": {"_eq": "x"}}}
        graphql = await hasura.update(
            "flow", where=where, set={"name": "y"}, run_mutation=False
        )
        assert graphql["variables"] == [
            Variable(name="update_where", type="flow_bool_exp!", value=where),
            Variable(name="update_set", type="flow_set_input", value={"name": "y"}),
        ]

    async def test_generate_gql_update_flows_increment(self):
        graphql = await hasura.update(
            "flow", where={}, increment={"age": 1}, run_mutation=False
        )
        expected_query = """
            update: update_flow(where: $update_where, _inc: $update_inc) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="update_where", type="flow_bool_exp!", value={}),
            Variable(name="update_inc", type="flow_inc_input", value={"age": 1}),
        ]

    async def test_alias(self):
        graphql = await hasura.update(
            "flow",
            where={},
            alias="x",
            set={"name": "x"},
            increment={"age": 1},
            run_mutation=False,
        )
        expected_query = """
            x: update_flow(where: $x_where, _set: $x_set, _inc: $x_inc) {
                affected_rows
            }
        """
        assert parse_graphql(graphql["query"]) == dedent(expected_query).strip()
        assert graphql["variables"] == [
            Variable(name="x_where", type="flow_bool_exp!", value={}),
            Variable(name="x_set", type="flow_set_input", value={"name": "x"}),
            Variable(name="x_inc", type="flow_inc_input", value={"age": 1}),
        ]


class TestUpdate:
    @pytest.fixture(autouse=True)
    async def monkeypatch_post_query_variables(self, monkeypatch):
        """
        Patches request.post so that await hasura.execute() returns a Box containing the
        GraphQL query and variables.
        """
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=dict(
                            update=Box(
                                query=kwargs["json"]["query"],
                                variables=kwargs["json"]["variables"],
                            )
                        )
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)

    async def test_where_must_be_provided(self):
        with pytest.raises(TypeError) as exc:
            await hasura.update("flow", set={})
        assert "must be provided" in str(exc.value)

    async def test_where_must_be_dict(self):
        with pytest.raises(TypeError) as exc:
            await hasura.update("flow", where=1)
        assert "must be provided" in str(exc.value)

    async def test_where_can_be_none_if_id_is_provided(self):
        assert await hasura.update("flow", id=1, set={})

    async def test_op_must_be_provided(self):
        with pytest.raises(ValueError) as exc:
            await hasura.update("flow", where={})
        assert "operation must be provided" in str(exc.value)

    async def test_generate_mutation(self):
        result = await hasura.update("flow", where={"color": "red"}, set={"name": "x"})
        expected_query = dedent(
            """
            mutation($update_where: flow_bool_exp!, $update_set: flow_set_input) {
                update: update_flow(where: $update_where, _set: $update_set) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(
            update_where={"color": "red"}, update_set={"name": "x"}
        )

    async def test_generate_mutation_selection_set(self):
        result = await hasura.update(
            "flow",
            where={"color": "red"},
            set={"name": "x"},
            selection_set={"returning": ["id", "name"]},
        )
        expected_query = dedent(
            """
             mutation($update_where: flow_bool_exp!, $update_set: flow_set_input) {
                update: update_flow(where: $update_where, _set: $update_set) {
                    returning {
                        id
                        name
                    }
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(
            update_where={"color": "red"}, update_set={"name": "x"}
        )

    async def test_id_creates_where(self):
        result = await hasura.update("flow", id="1", set={"name": "x"})
        expected_query = dedent(
            """
            mutation($update_where: flow_bool_exp!, $update_set: flow_set_input) {
                update: update_flow(where: $update_where, _set: $update_set) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(
            update_where={"id": {"_eq": "1"}}, update_set={"name": "x"}
        )

    async def test_generate_increment_variables(self):
        result = await hasura.update("flow", id="1", increment={"name": 1})
        expected_query = dedent(
            """
            mutation($update_where: flow_bool_exp!, $update_inc: flow_inc_input) {
                update: update_flow(where: $update_where, _inc: $update_inc) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.query == expected_query
        assert result.variables == dict(
            update_where={"id": {"_eq": "1"}}, update_inc={"name": 1}
        )


class TestRunMutationsInTransaction:
    @pytest.fixture(autouse=True)
    async def monkeypatch_post_query_variables(self, monkeypatch):
        """
        Patches request.post so that await hasura.execute() returns a Box containing the
        GraphQL query and variables.
        """
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=Box(
                            query=kwargs["json"]["query"],
                            variables=kwargs["json"]["variables"],
                        )
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)

    async def test_run_one_mutation_in_transaction(self):
        insert_graphql = await hasura.insert(
            "flow", objects=[{"x": 1}], run_mutation=False
        )
        result = await hasura.execute_mutations_in_transaction([insert_graphql])

        expected_query = dedent(
            """
            mutation($insert_objects: [flow_insert_input!]!) {
                insert: insert_flow(objects: $insert_objects) {
                    affected_rows
                }
            }
            """
        ).strip()
        assert result.data.query == expected_query
        assert result.data.variables == dict(insert_objects=[{"x": 1}])

    async def test_run_two_mutations_in_transaction(self):
        insert_graphql = await hasura.insert(
            "flow", objects=[{"x": 1}], run_mutation=False
        )
        update_graphql = await hasura.update(
            "flow",
            where={"x": {"_eq": 1}},
            set={"x": 2},
            selection_set={"returning": {"id"}},
            run_mutation=False,
        )
        result = await hasura.execute_mutations_in_transaction(
            [insert_graphql, update_graphql]
        )

        expected_query = dedent(
            """
            mutation($insert_objects: [flow_insert_input!]!, $update_where: flow_bool_exp!, $update_set: flow_set_input) {
                insert: insert_flow(objects: $insert_objects) {
                    affected_rows
                }
                update: update_flow(where: $update_where, _set: $update_set) {
                    returning {
                        id
                    }
                }
            }
            """
        ).strip()
        assert result.data.query == expected_query
        assert result.data.variables == dict(
            insert_objects=[{"x": 1}],
            update_where={"x": {"_eq": 1}},
            update_set={"x": 2},
        )

    async def test_run_two_mutations_in_transaction_with_aliases(self):
        insert_graphql_1 = await hasura.insert(
            "flow", objects=[{"x": 1}], alias="insert_1", run_mutation=False
        )
        insert_graphql_2 = await hasura.insert(
            "flow",
            objects=[{"x": 2}],
            alias="insert_2",
            selection_set={"returning": {"id"}},
            run_mutation=False,
        )
        result = await hasura.execute_mutations_in_transaction(
            [insert_graphql_1, insert_graphql_2]
        )

        expected_query = dedent(
            """
            mutation($insert_1_objects: [flow_insert_input!]!, $insert_2_objects: [flow_insert_input!]!) {
                insert_1: insert_flow(objects: $insert_1_objects) {
                    affected_rows
                }
                insert_2: insert_flow(objects: $insert_2_objects) {
                    returning {
                        id
                    }
                }
            }
            """
        ).strip()
        assert result.data.query == expected_query
        assert result.data.variables == dict(
            insert_1_objects=[{"x": 1}], insert_2_objects=[{"x": 2}]
        )


class TestExecuteResult:
    @pytest.fixture(autouse=True)
    async def monkeypatch_post_data(self, monkeypatch):
        """
        Patches request.post so that await hasura.execute() returns data
        """
        post = CoroutineMock(
            side_effect=lambda *args, **kwargs: MagicMock(
                json=MagicMock(
                    side_effect=lambda: dict(
                        data=dict(x=1, y=[dict(a=1, b=2), dict(a=1, b=2)], z=dict(c=3))
                    )
                )
            )
        )
        monkeypatch.setattr("httpx.post", post)

    async def test_execute_respects_as_box(self):
        result = await HasuraClient().execute("query { x }")
        assert isinstance(result, Box)
        assert result.data.x == 1
        assert isinstance(result.data.y[0], Box)
        assert result.data.y[0].a == 1

    async def test_execute_respects_not_as_box(self):
        result = await HasuraClient().execute("query { x }", as_box=False)
        assert isinstance(result, dict) and not isinstance(result, Box)
        assert result["data"]["x"] == 1
        assert isinstance(result["data"]["y"][0], dict) and not isinstance(
            result["data"]["y"][0], Box
        )
        assert result["data"]["y"][0]["a"] == 1
