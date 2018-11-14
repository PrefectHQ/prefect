from textwrap import dedent
import pytest
from prefect.utilities.graphql import GQLObject, parse_graphql, parse_graphql_arguments
from collections import OrderedDict


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
    args = parse_graphql_arguments({"where": {"x": {"eq": '"1"'}}})
    assert args == 'where: { x: { eq: "1" } }'


def test_arguments_are_parsed_automatically():
    account = Account()({"where": {"x": {"eq": '"1"'}}})
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
