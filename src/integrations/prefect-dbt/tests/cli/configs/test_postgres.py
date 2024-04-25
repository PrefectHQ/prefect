from prefect_sqlalchemy import (
    ConnectionComponents,
    DatabaseCredentials,
    SqlAlchemyConnector,
    SyncDriver,
)
from pydantic import VERSION as PYDANTIC_VERSION

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import SecretStr
else:
    from pydantic import SecretStr

from prefect_dbt.cli.configs import PostgresTargetConfigs


def test_postgres_target_configs_get_configs():
    credentials = DatabaseCredentials(
        driver=SyncDriver.POSTGRESQL_PSYCOPG2,
        username="prefect",
        password="prefect_password",
        database="postgres",
        host="host",
        port=8080,
    )
    configs = PostgresTargetConfigs(schema="schema", credentials=credentials)
    actual = configs.get_configs()
    expected = {
        "type": "postgres",
        "schema": "schema",
        "threads": 4,
        "dbname": "postgres",
        "user": "prefect",
        "password": "prefect_password",
        "host": "host",
        "port": 8080,
    }
    for k, v in actual.items():
        actual_v = v.get_secret_value() if isinstance(v, SecretStr) else v
        expected_v = expected[k]
        assert actual_v == expected_v


def test_postgres_target_configs_get_configs_for_sqlalchemy_connector():
    configs = PostgresTargetConfigs(
        credentials=SqlAlchemyConnector(
            connection_info=ConnectionComponents(
                driver="postgresql+psycopg2",
                database="postgres",
                username="prefect",
                password="prefect_password",
                host="host",
                port=8080,
                query={"a": "query"},
            ),
            kwarg_that_shouldnt_show_up=True,
        ),
        schema="schema",
        extras={"retries": 1},
    )
    actual = configs.get_configs()
    expected = {
        "type": "postgres",
        "schema": "schema",
        "threads": 4,
        "dbname": "postgres",
        "user": "prefect",
        "password": "prefect_password",
        "host": "host",
        "port": 8080,
        "retries": 1,
    }
    for k, v in actual.items():
        actual_v = v.get_secret_value() if isinstance(v, SecretStr) else v
        expected_v = expected[k]
        assert actual_v == expected_v
    assert hasattr(configs.credentials, "kwarg_that_shouldnt_show_up")
    assert "kwarg_that_shouldnt_show_up" not in actual.keys()
    assert hasattr(configs.credentials.connection_info, "query")
    assert "query" not in actual.keys()
