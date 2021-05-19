import pytest
from unittest.mock import MagicMock, call

from prefect.backend.kv_store import set_key_value, get_key_value, delete_key, list_keys
from prefect.utilities.exceptions import ClientError
from prefect.utilities.graphql import GraphQLResult


class TestSetKeyValue:
    def test_set_key_value_raises_on_server_backend(self, server_api):
        with pytest.raises(ClientError):
            set_key_value(key="foo", value="bar")

    def test_set_key_value_calls_client_mutation_correctly(
        self, monkeypatch, cloud_api
    ):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    set_key_value=GraphQLResult({"id": "123"}),
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.backend.kv_store.Client", client)

        key_value_id = set_key_value(key="foo", value="bar")
        client.return_value.graphql.assert_called_with(
            query={
                "mutation($input: set_key_value_input!)": {
                    "set_key_value(input: $input)": {"id"}
                }
            },
            variables={"input": {"key": "foo", "value": "bar"}},
        )
        assert key_value_id == "123"


class TestGetKeyValue:
    def test_get_key_value_raises_on_server_backend(self, server_api):
        with pytest.raises(ClientError):
            get_key_value(key="foo")

    def test_get_key_value_calls_client_query_correctly(self, monkeypatch, cloud_api):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    key_value=[GraphQLResult({"value": "bar"})],
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.backend.kv_store.Client", client)

        value = get_key_value(key="foo")
        client.return_value.graphql.assert_called_with(
            {"query": {'key_value(where: { key: { _eq: "foo" } })': {"value"}}}
        )
        assert value == "bar"

    def test_get_key_value_raises_if_key_not_found(self, monkeypatch, cloud_api):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    key_value=[],
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.backend.kv_store.Client", client)

        with pytest.raises(ValueError):
            get_key_value(key="foo")

        client.return_value.graphql.assert_called_with(
            {"query": {'key_value(where: { key: { _eq: "foo" } })': {"value"}}}
        )


class TestDeleteKeyValue:
    def test_delete_key_value_raises_on_server_backend(self, server_api):
        with pytest.raises(ClientError):
            delete_key(key="foo")

    def test_get_key_value_calls_client_query_correctly(self, monkeypatch, cloud_api):
        key_value_id_gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    key_value=[GraphQLResult({"id": "123"})],
                )
            )
        )
        delete_key_value_gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    delete_key_value=GraphQLResult({"success": True}),
                )
            )
        )

        def fake_graphql_responses(*args, **kwargs):
            if "query" in kwargs["query"]:
                return key_value_id_gql_return.return_value
            return delete_key_value_gql_return.return_value

        client = MagicMock()
        client.return_value.graphql.side_effect = fake_graphql_responses
        monkeypatch.setattr("prefect.backend.kv_store.Client", client)

        success = delete_key(key="foo")

        assert success

        assert client.return_value.graphql.call_args_list == [
            call(
                query={"query": {'key_value(where: { key: { _eq: "foo" } })': {"id"}}}
            ),
            call(
                query={
                    "mutation($input: delete_key_value_input!)": {
                        "delete_key_value(input: $input)": {"success"}
                    }
                },
                variables={"input": {"key_value_id": "123"}},
            ),
        ]

    def test_delete_key_value_raises_if_key_not_found(self, monkeypatch, cloud_api):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    key_value=[],
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.backend.kv_store.Client", client)

        with pytest.raises(ValueError):
            delete_key(key="foo")

        client.return_value.graphql.assert_called_with(
            query={"query": {'key_value(where: { key: { _eq: "foo" } })': {"id"}}}
        )


class TestListKeyValue:
    def test_list_key_value_raises_on_server_backend(self, server_api):
        with pytest.raises(ClientError):
            list_keys()

    def test_list_key_value_calls_client_mutation_correctly(
        self, monkeypatch, cloud_api
    ):
        gql_return = MagicMock(
            return_value=MagicMock(
                data=GraphQLResult(
                    key_value=[
                        GraphQLResult({"key": "foo"}),
                        GraphQLResult({"key": "foo2"}),
                    ],
                )
            )
        )
        client = MagicMock()
        client.return_value.graphql = gql_return
        monkeypatch.setattr("prefect.backend.kv_store.Client", client)

        keys = list_keys()
        client.return_value.graphql.assert_called_with(
            {"query": {"key_value(order_by: {key: asc})": {"key"}}}
        )
        assert keys == ["foo", "foo2"]
