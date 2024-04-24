import os
from unittest.mock import MagicMock

import pytest
from prefect_snowflake.credentials import SnowflakeCredentials

from prefect.testing.utilities import prefect_test_harness


def _read_test_file(name: str) -> bytes:
    """
    Args:
        name: File to load from test_data folder.

    Returns:
        File content as binary.
    """
    full_name = os.path.join(os.path.split(__file__)[0], "test_data", name)
    with open(full_name, "rb") as fd:
        return fd.read()


@pytest.fixture(scope="session", autouse=True)
def prefect_db():
    """
    Sets up test harness for temporary DB during test runs.
    """
    with prefect_test_harness():
        yield


@pytest.fixture(autouse=True)
def reset_object_registry():
    """
    Ensures each test has a clean object registry.
    """
    from prefect.context import PrefectObjectRegistry

    with PrefectObjectRegistry():
        yield


@pytest.fixture()
def credentials_params():
    return {
        "account": "account",
        "user": "user",
        "password": "password",
    }


@pytest.fixture()
def connector_params(credentials_params):
    snowflake_credentials = SnowflakeCredentials(**credentials_params)
    _connector_params = {
        "schema": "schema_input",
        "database": "database",
        "warehouse": "warehouse",
        "credentials": snowflake_credentials,
    }
    return _connector_params


@pytest.fixture()
def private_credentials_params():
    return {
        "account": "account",
        "user": "user",
        "password": "letmein",
        "private_key": _read_test_file("test_cert.p8"),
    }


@pytest.fixture()
def private_key_path_credentials_params():
    return {
        "account": "account",
        "user": "user",
        "private_key_path": "path/to/private/key",
        "private_key_passphrase": "letmein",
    }


@pytest.fixture()
def private_connector_params(private_credentials_params):
    snowflake_credentials = SnowflakeCredentials(**private_credentials_params)
    _connector_params = {
        "schema": "schema_input",
        "database": "database",
        "warehouse": "warehouse",
        "credentials": snowflake_credentials,
    }
    return _connector_params


@pytest.fixture()
def private_no_pass_credentials_params():
    return {
        "account": "account",
        "user": "user",
        "password": "letmein",
        "private_key": _read_test_file("test_cert_no_pass.p8"),
    }


@pytest.fixture()
def private_no_pass_connector_params(private_no_pass_credentials_params):
    snowflake_credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
    _connector_params = {
        "schema": "schema_input",
        "database": "database",
        "warehouse": "warehouse",
        "credentials": snowflake_credentials,
    }
    return _connector_params


@pytest.fixture()
def private_malformed_credentials_params():
    return {
        "account": "account",
        "user": "user",
        "password": "letmein",
        "private_key": _read_test_file("test_cert_malformed_format.p8"),
    }


@pytest.fixture(autouse=True)
def snowflake_connect_mock(monkeypatch):
    mock_cursor = MagicMock(name="cursor mock")
    results = iter([0, 1, 2, 3, 4])
    mock_cursor.return_value.fetchone.side_effect = lambda: (next(results),)
    mock_cursor.return_value.fetchmany.side_effect = lambda size: list(
        (next(results),) for i in range(size)
    )
    mock_cursor.return_value.fetchall.side_effect = lambda: [
        (result,) for result in results
    ]

    mock_connection = MagicMock(name="connection mock")
    mock_connection.return_value.is_still_running.return_value = False
    mock_connection.return_value.cursor = mock_cursor

    monkeypatch.setattr("snowflake.connector.connect", mock_connection)
    return mock_connection
