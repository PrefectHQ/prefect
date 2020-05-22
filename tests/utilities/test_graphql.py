import json
import uuid
from collections import OrderedDict
from textwrap import dedent

import pytest
from box import Box

from prefect.engine.state import Pending
from prefect.utilities.graphql import (
    EnumValue,
    GQLObject,
    GraphQLResult,
    LiteralSetValue,
    compress,
    decompress,
    parse_graphql,
    parse_graphql_arguments,
    with_args,
)


class Account(GQLObject):
    id = "id"
    name = "name"


class User(GQLObject):
    id = "id"
    name = "name"
    account = Account("account")


# avoid circular assignment since User isn't available when Account is created
Account.users = User("users")


class Query(GQLObject):
    users = User("users")
    accounts = Account("accounts")


class Mutation(GQLObject):
    createUser = "createUser"
    createAccount = "createAccount"


def verify(query, expected):
    assert parse_graphql(query) == dedent(expected).strip()


def test_default_gqlo_name_is_lowercase():
    assert str(Account()) == "account"


def test_parse_graphql_dedents_and_strips():
    query = """

        hi
            there

    """
    assert parse_graphql(query) == "hi\n    there"


def test_parse_arguments():
    args = parse_graphql_arguments({"where": {"x": {"eq": "1"}}})
    assert args == 'where: { x: { eq: "1" } }'


def test_parse_string_arguments():
    args = parse_graphql_arguments({"where": {"x": {"eq": r"a 'b' c"}}})
    assert args == "where: { x: { eq: \"a 'b' c\" } }"


def test_parse_bool_arguments():
    # test that bool args are matched, even if follwed by a comma
    # ordering issues in earlier python versions
    inner = OrderedDict()
    inner["x"] = True
    inner["y"] = False

    args = parse_graphql_arguments({"where": inner})
    assert args == "where: { x: true, y: false }"


def test_parse_none_arguments():
    # test that nulls are matched, even when followed by a comma

    # ordering issues in earlier python versions
    inner = OrderedDict()
    inner["x"] = None
    inner["y"] = None
    args = parse_graphql_arguments({"where": inner})
    assert args == "where: { x: null, y: null }"


def test_parse_json_arguments():
    arg = json.dumps({"a": "b", "c": [1, "d"]}, sort_keys=True)
    gql_args = parse_graphql_arguments({"where": {"x": {"eq": arg}}})
    assert gql_args == r'where: { x: { eq: "{\"a\": \"b\", \"c\": [1, \"d\"]}" } }'


def test_parse_nested_string():
    gql_args = parse_graphql_arguments(
        {"input": {"x": json.dumps({"a": 1, "b": 2}, sort_keys=True)}}
    )
    assert gql_args == r'input: { x: "{\"a\": 1, \"b\": 2}" }'


def test_with_args():
    verify(
        query={"query": {with_args("accounts", {"where": {"x": 1}}): {"id"}}},
        expected="""
            query {
                accounts(where: { x: 1 }) {
                    id
                }
            }
        """,
    )


def test_gqlo_with_args():
    verify(
        query={"query": {with_args(Account(), {"where": {"x": 1}}): {"id"}}},
        expected="""
            query {
                account(where: { x: 1 }) {
                    id
                }
            }
        """,
    )


def test_arguments_are_parsed_automatically():
    account = Account()({"where": {"x": {"eq": "1"}}})
    assert str(account) == 'account(where: { x: { eq: "1" } })'


def test_string_query_1():
    verify(
        query={"query": {"users": ["id", "name"]}},
        expected="""
            query {
                users {
                    id
                    name
                }
            }
        """,
    )


def test_string_query_2():
    verify(
        query={"query": {"users": [{"id(arg1: 1, arg2: 2)": ["result"]}, "name"]}},
        expected="""
            query {
                users {
                    id(arg1: 1, arg2: 2) {
                        result
                    }
                    name
                }
            }
        """,
    )


def test_string_query_3():

    # do this to ensure field order on Python < 3.6
    inner = OrderedDict()
    inner["users"] = ["id", "name"]
    inner["accounts"] = ["id", "name"]

    verify(
        query={"query": inner},
        expected="""
            query {
                users {
                    id
                    name
                }
                accounts {
                    id
                    name
                }
            }
        """,
    )


def test_dict_keys_query_1():
    dict_keys = {"id": True}
    verify(
        query={"query": {"users": dict_keys.keys()}},
        expected="""
            query {
                users {
                    id
                }
            }
        """,
    )


def test_dict_values_query_1():
    dict_values = {1: "id"}
    verify(
        query={"query": {"users": dict_values.values()}},
        expected="""
            query {
                users {
                    id
                }
            }
        """,
    )


def test_gqlo_1():
    verify(
        query={"query": {Query.accounts: [Account.id, Account.name]}},
        expected="""
            query {
                accounts {
                    id
                    name
                }
            }
            """,
    )


def test_gqlo_2():

    # do this to ensure field order on Python < 3.6
    inner = OrderedDict()
    inner[Query.accounts] = [Account.id, Account.name]
    inner[Query.users] = [User.id, User.name]

    verify(
        query={"query": inner},
        expected="""
            query {
                accounts {
                    id
                    name
                }
                users {
                    id
                    name
                }
            }
            """,
    )


def test_gqlo_is_callable_for_arguments():
    verify(
        query={"query": {Query.accounts("where: {id: 5}"): [Account.id, Account.name]}},
        expected="""
            query {
                accounts(where: {id: 5}) {
                    id
                    name
                }
            }
            """,
    )


def test_gqlo_is_callable_for_dict_arguments():
    verify(
        query={
            "query": {Query.accounts({"where": {"id": 5}}): [Account.id, Account.name]}
        },
        expected="""
            query {
                accounts(where: { id: 5 }) {
                    id
                    name
                }
            }
            """,
    )


def test_nested_gqlo():
    verify(
        query={
            "query": {
                Query.accounts: {
                    Query.accounts.users: {
                        Query.accounts.users.account: Query.accounts.users.account.id
                    }
                }
            }
        },
        expected="""
            query {
                accounts {
                    users {
                        account {
                            id
                        }
                    }
                }
            }
        """,
    )


def test_use_true_to_indicate_field_name():
    # do this to ensure field order on Python < 3.6
    inner = OrderedDict()
    inner["id"] = True
    inner["authors"] = {"id"}

    verify(
        query={"query": {"books": inner}},
        expected="""
            query {
                books {
                    id
                    authors {
                        id
                    }
                }
            }
        """,
    )


def test_box_query_parsing():
    verify(
        query=Box(query=Box(books={"id"})),
        expected="""
            query {
                books {
                    id
                }
            }
        """,
    )


def test_pass_box_as_args():
    verify(
        query={
            "query": {
                with_args("books", Box(author=Box(name=Box(first="first")))): {"id"}
            }
        },
        expected="""
            query {
                books(author: { name: { first: "first" } }) {
                    id
                }
            }
        """,
    )


def test_empty_dict_in_arguments():
    assert parse_graphql_arguments({"where": {}}) == "where: {}"


def test_dict_keys_in_arguments():
    x = {"a": 1, "b": 2}
    assert parse_graphql_arguments({"checks": x.keys()}) in [
        'checks: ["a", "b"]',
        'checks: ["b", "a"]',
    ]


def test_dict_values_in_arguments():
    x = {"a": 1, "b": 2}
    assert parse_graphql_arguments({"checks": x.values()}) in [
        "checks: [1, 2]",
        "checks: [2, 1]",
    ]


def test_enum_value_in_arguments():
    query = parse_graphql_arguments({"where": {"color": EnumValue("red")}})
    assert query == "where: { color: red }"


def test_set_value_in_arguments():
    query = parse_graphql_arguments(
        {"where": {"color": LiteralSetValue(["red", "blue"])}}
    )
    assert query == 'where: { color: "{red, blue}" }'


def test_set_value_in_arguments_with_one_value():
    query = parse_graphql_arguments({"where": {"color": LiteralSetValue(["red"])}})
    assert query == 'where: { color: "{red}" }'


def test_uuid_value_in_arguments():
    id = uuid.uuid4()
    query = parse_graphql_arguments({"id": id})
    assert query == 'id: "{}"'.format(id)


def test_compress():
    result = compress({"test": 42})
    assert isinstance(result, str)


def test_decompress():
    test_str = compress({"test": 42})
    result = decompress(test_str)
    assert isinstance(result, dict)


@pytest.mark.parametrize(
    "obj",
    ["abc", 42, None, ["testlist", "stilltesting"], {"testing1234": 123}, [1, 2, 3]],
)
def test_compression_back_translation(obj):
    assert decompress(compress(obj)) == obj


def test_graphql_result_has_nice_repr():
    expected = """{\n    "flow_run": {\n        "flow": [\n            {\n                "id": 1\n            },\n            {\n                "version": 2\n            }\n        ]\n    }\n}"""
    gql = {"flow_run": {"flow": [{"id": 1}, {"version": 2}]}}
    res = GraphQLResult(gql)
    assert repr(res) == expected


def test_graphql_repr_falls_back_to_dict_repr():
    gql = {"flow_run": Pending("test")}
    res = GraphQLResult(gql)
    assert repr(res) == """{'flow_run': <Pending: "test">}"""
