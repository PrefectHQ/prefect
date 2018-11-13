from textwrap import dedent
import pytest
from prefect.utilities.graphql import GQLObject, parse_graphql


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
    parsed = parse_graphql(query)
    assert dedent(parsed).strip() == dedent(expected).strip()


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
    verify(
        query={"query": {"users": ["id", "name"], "accounts": ["id", "name"]}},
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
    verify(
        query={
            "query": {
                Query.accounts: [Account.id, Account.name],
                Query.users: [User.id, User.name],
            }
        },
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
