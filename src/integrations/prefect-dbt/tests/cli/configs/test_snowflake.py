from pathlib import Path

from prefect_dbt.cli.configs import SnowflakeTargetConfigs
from prefect_snowflake.credentials import SnowflakeCredentials
from prefect_snowflake.database import SnowflakeConnector
from pydantic import SecretBytes, SecretStr


def test_snowflake_target_configs_get_configs():
    credentials = SnowflakeCredentials(
        account="account",
        user="user",
        password="password",
    )
    snowflake_connector = SnowflakeConnector(
        schema="schema",
        database="database",
        warehouse="warehouse",
        credentials=credentials,
    )
    configs = SnowflakeTargetConfigs(
        connector=snowflake_connector, extras={"retry_on_database_errors": True}
    )

    actual = configs.get_configs()
    expected = dict(
        account="account",
        user="user",
        password="password",
        type="snowflake",
        schema="schema",
        database="database",
        warehouse="warehouse",
        authenticator="snowflake",
        retry_on_database_errors=True,
        threads=4,
    )
    for k, v in actual.items():
        actual_v = (
            v.get_secret_value() if isinstance(v, (SecretBytes, SecretStr)) else v
        )
        expected_v = expected[k]
        assert actual_v == expected_v


def test_snowflake_target_configs_get_configs_private_key_path():
    credentials = SnowflakeCredentials(
        account="account",
        user="user",
        private_key_path=Path("path/to/key"),
    )
    snowflake_connector = SnowflakeConnector(
        schema="schema",
        database="database",
        warehouse="warehouse",
        credentials=credentials,
    )
    configs = SnowflakeTargetConfigs(
        connector=snowflake_connector, extras={"retry_on_database_errors": True}
    )

    actual = configs.get_configs()
    expected = dict(
        account="account",
        user="user",
        private_key_path=str(Path("path/to/key")),
        type="snowflake",
        schema="schema",
        database="database",
        warehouse="warehouse",
        authenticator="snowflake",
        retry_on_database_errors=True,
        threads=4,
    )
    for k, v in actual.items():
        actual_v = (
            v.get_secret_value() if isinstance(v, (SecretBytes, SecretStr)) else v
        )
        expected_v = expected[k]
        assert actual_v == expected_v


def test_snowflake_target_configs_allow_field_overrides():
    credentials = SnowflakeCredentials(
        user="user",
        account="account.region.aws",
        password="my_password",
        role="role",
    )

    connector = SnowflakeConnector(
        schema="public",
        database="database",
        warehouse="warehouse",
        credentials=credentials,
    )

    target_configs = SnowflakeTargetConfigs(
        connector=connector,
        schema="OVERRIDE",
        extras={"database": "my_database"},
        allow_field_overrides=True,
    )
    actual = target_configs.get_configs()
    expected = {
        "schema": "OVERRIDE",
        "type": "snowflake",
        "threads": 4,
        "account": "account.region.aws",
        "user": "user",
        "password": "my_password",
        "authenticator": "snowflake",
        "role": "role",
        "database": "my_database",
        "warehouse": "warehouse",
    }
    assert actual == expected


def test_snowflake_target_configs_get_configs_private_key():
    credentials = SnowflakeCredentials(
        account="account",
        user="user",
        private_key="some-private-key",
    )
    snowflake_connector = SnowflakeConnector(
        schema="schema",
        database="database",
        warehouse="warehouse",
        credentials=credentials,
    )
    configs = SnowflakeTargetConfigs(
        connector=snowflake_connector, extras={"retry_on_database_errors": True}
    )

    actual = configs.get_configs()
    expected = dict(
        account="account",
        user="user",
        private_key="some-private-key",
        type="snowflake",
        schema="schema",
        database="database",
        warehouse="warehouse",
        authenticator="snowflake",
        retry_on_database_errors=True,
        threads=4,
    )
    for k, v in actual.items():
        actual_v = (
            v.get_secret_value() if isinstance(v, (SecretBytes, SecretStr)) else v
        )
        expected_v = expected[k]
        assert actual_v == expected_v
