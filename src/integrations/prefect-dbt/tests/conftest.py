import json
from unittest.mock import MagicMock

import pytest
from prefect_dbt.cli.configs import (
    BigQueryTargetConfigs,
    PostgresTargetConfigs,
    SnowflakeTargetConfigs,
)
from prefect_dbt.cli.configs.base import GlobalConfigs, TargetConfigs
from prefect_dbt.cli.credentials import DbtCliProfile
from prefect_dbt.cloud.credentials import DbtCloudCredentials
from prefect_gcp import GcpCredentials
from prefect_snowflake import SnowflakeConnector, SnowflakeCredentials
from prefect_sqlalchemy import (
    ConnectionComponents,
    DatabaseCredentials,
    SqlAlchemyConnector,
    SyncDriver,
)

from prefect.testing.utilities import prefect_test_harness


@pytest.fixture
def dbt_cloud_credentials():
    return DbtCloudCredentials(api_key="my_api_key", account_id=123456789)


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


@pytest.fixture(autouse=True)
def google_auth_mock(monkeypatch):
    """
    Mocks out the google.auth module.
    """
    google_auth_default_mock = MagicMock()
    monkeypatch.setattr("google.auth.default", google_auth_default_mock)


@pytest.fixture
def dbt_cli_profile():
    target_configs = TargetConfigs(
        type="snowflake",
        schema="my_schema",
        threads=4,
        extras=dict(
            account="account",
            user="user",
            password="password",
            role="role",
            database="database",
            warehouse="warehouse",
            client_session_keep_alive=False,
            query_tag="query_tag",
        ),
    )
    global_configs = GlobalConfigs(
        send_anonymous_usage_stats=False,
        use_colors=True,
        partial_parse=False,
        printer_width=88,
        write_json=True,
        warn_error=False,
        log_format=True,
        debug=True,
        version_check=True,
        fail_fast=True,
        use_experimental_parser=True,
        static_parser=False,
    )
    return DbtCliProfile(
        name="jaffle_shop",
        target="dev",
        target_configs=target_configs,
        global_configs=global_configs,
    )


@pytest.fixture
def dbt_cli_profile_bare():
    target_configs = TargetConfigs(
        type="custom", schema="my_schema", extras={"account": "fake"}
    )
    return DbtCliProfile(
        name="prefecto",
        target="testing",
        target_configs=target_configs,
    )


@pytest.fixture()
def service_account_info_dict(monkeypatch):
    monkeypatch.setattr(
        "google.auth.crypt._cryptography_rsa.serialization.load_pem_private_key",
        lambda *args, **kwargs: args[0],
    )
    _service_account_info = {
        "project_id": "service_project",
        "token_uri": "my-token-uri",
        "client_email": "my-client-email",
        "private_key": "my-private-key",
    }
    return _service_account_info


@pytest.fixture()
def service_account_file(monkeypatch, tmp_path, service_account_info_dict):
    monkeypatch.setattr(
        "google.auth.crypt._cryptography_rsa.serialization.load_pem_private_key",
        lambda *args, **kwargs: args[0],
    )
    _service_account_file = tmp_path / "gcp.json"
    with open(_service_account_file, "w") as f:
        json.dump(service_account_info_dict, f)
    return _service_account_file


@pytest.fixture
def google_auth(monkeypatch):
    google_auth_mock = MagicMock(name="google_auth")
    default_credentials_mock = MagicMock(
        name="default_credentials",
        quota_project_id="my_project",
    )
    google_auth_mock.default.side_effect = lambda *args, **kwargs: (
        default_credentials_mock,
        None,
    )
    monkeypatch.setattr("google.auth", google_auth_mock)
    return google_auth_mock


@pytest.fixture
def snowflake_target_configs():
    credentials = SnowflakeCredentials(
        user="user",
        password="password",
        account="account.region.aws",
        role="role",
    )
    connector = SnowflakeConnector(
        schema="public",
        database="database",
        warehouse="warehouse",
        credentials=credentials,
    )
    target_configs = SnowflakeTargetConfigs(connector=connector)
    return target_configs


@pytest.fixture
def postgres_target_configs():
    credentials = DatabaseCredentials(
        driver=SyncDriver.POSTGRESQL_PSYCOPG2,
        username="prefect",
        password="prefect_password",
        database="postgres",
        host="host",
        port=8080,
    )
    target_configs = PostgresTargetConfigs(schema="my_schema", credentials=credentials)
    return target_configs


def sqlalchemy_target_configs():
    credentials = SqlAlchemyConnector(
        connection_info=ConnectionComponents(
            driver=SyncDriver.POSTGRESQL_PSYCOPG2,
            database="postgres",
            username="prefect",
            password="prefect_password",
        )
    )
    target_configs = PostgresTargetConfigs(schema="my_schema", credentials=credentials)
    return target_configs


@pytest.fixture
def bigquery_target_configs(service_account_info_dict):
    credentials = GcpCredentials(service_account_info=service_account_info_dict)
    target_configs = BigQueryTargetConfigs(credentials=credentials, schema="my_schema")
    return target_configs


@pytest.fixture
def class_target_configs():
    target_configs = TargetConfigs(type="type", schema="my_schema", threads=4)
    return target_configs


@pytest.fixture
def dict_target_configs():
    target_configs = dict(type="type", schema="my_schema", threads=4)
    return target_configs
