import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import flow
from prefect.utilities.filesystem import relative_path_to_current_platform

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import SecretBytes, SecretStr
else:
    from pydantic import SecretBytes, SecretStr

from prefect_snowflake.credentials import InvalidPemFormat, SnowflakeCredentials
from prefect_snowflake.database import SnowflakeConnector


def test_snowflake_credentials_init(credentials_params):
    snowflake_credentials = SnowflakeCredentials(**credentials_params)
    actual_credentials_params = snowflake_credentials.dict()
    for param in credentials_params:
        actual = actual_credentials_params[param]
        expected = credentials_params[param]
        if isinstance(actual, SecretStr):
            actual = actual.get_secret_value()
        assert actual == expected


def test_snowflake_credentials_validate_auth_kwargs(credentials_params):
    credentials_params_missing = credentials_params.copy()
    credentials_params_missing.pop("password")
    with pytest.raises(ValueError, match="One of the authentication keys"):
        SnowflakeCredentials(**credentials_params_missing)


def test_snowflake_credentials_validate_auth_kwargs_private_keys(credentials_params):
    credentials_params["private_key"] = "key"
    credentials_params["private_key_path"] = "keypath"
    with pytest.raises(ValueError, match="Do not provide both private_key and private"):
        SnowflakeCredentials(**credentials_params)


def test_snowflake_credentials_validate_auth_kwargs_private_key_password(
    credentials_params,
):
    credentials_params["private_key_passphrase"] = "key"
    with pytest.raises(ValueError, match="Do not provide both password and private_"):
        SnowflakeCredentials(**credentials_params)


def test_snowflake_credentials_validate_token_kwargs(credentials_params):
    credentials_params_missing = credentials_params.copy()
    credentials_params_missing.pop("password")
    credentials_params_missing["authenticator"] = "oauth"
    with pytest.raises(ValueError, match="If authenticator is set to `oauth`"):
        SnowflakeCredentials(**credentials_params_missing)

    # now test if passing both works
    credentials_params_missing["token"] = "some_token"
    assert SnowflakeCredentials(**credentials_params_missing)


def test_snowflake_credentials_validate_okta_endpoint_kwargs(credentials_params):
    credentials_params_missing = credentials_params.copy()
    credentials_params_missing.pop("password")
    credentials_params_missing["authenticator"] = "okta_endpoint"
    with pytest.raises(ValueError, match="If authenticator is set to `okta_endpoint`"):
        SnowflakeCredentials(**credentials_params_missing)

    # now test if passing both works
    credentials_params_missing["endpoint"] = "https://account_name.okta.com"
    snowflake_credentials = SnowflakeCredentials(**credentials_params_missing)
    assert snowflake_credentials.endpoint == "https://account_name.okta.com"


def test_snowflake_credentials_support_deprecated_okta_endpoint(credentials_params):
    credentials_params_missing = credentials_params.copy()
    credentials_params_missing.pop("password")
    credentials_params_missing["authenticator"] = "okta_endpoint"
    credentials_params_missing["okta_endpoint"] = "deprecated.com"
    snowflake_credentials = SnowflakeCredentials(**credentials_params_missing)
    assert snowflake_credentials.endpoint == "deprecated.com"


def test_snowflake_credentials_support_endpoint_overrides_okta_endpoint(
    credentials_params,
):
    credentials_params_missing = credentials_params.copy()
    credentials_params_missing.pop("password")
    credentials_params_missing["authenticator"] = "okta_endpoint"
    credentials_params_missing["okta_endpoint"] = "deprecated.com"
    credentials_params_missing["endpoint"] = "new.com"
    snowflake_credentials = SnowflakeCredentials(**credentials_params_missing)
    assert snowflake_credentials.endpoint == "new.com"


def test_snowflake_private_credentials_init(private_credentials_params):
    snowflake_credentials = SnowflakeCredentials(**private_credentials_params)
    actual_credentials_params = snowflake_credentials.dict()
    for param in private_credentials_params:
        actual = actual_credentials_params[param]
        expected = private_credentials_params[param]
        if isinstance(actual, (SecretStr, SecretBytes)):
            actual = actual.get_secret_value()
        if sys.platform != "win32":
            assert actual == expected


def test_snowflake_private_credentials_malformed_certificate(
    private_credentials_params, private_malformed_credentials_params
):
    correct = SnowflakeCredentials(**private_credentials_params)
    malformed = SnowflakeCredentials(**private_malformed_credentials_params)
    c1 = correct.resolve_private_key()
    c2 = malformed.resolve_private_key()
    assert isinstance(c1, bytes)
    assert isinstance(c2, bytes)
    assert c1 == c2


def test_snowflake_private_credentials_invalid_certificate(private_credentials_params):
    private_credentials_params["private_key"] = "---- INVALID CERTIFICATE ----"
    with pytest.raises(InvalidPemFormat):
        SnowflakeCredentials(**private_credentials_params).resolve_private_key()


def test_snowflake_credentials_validate_private_key_password(
    private_credentials_params,
):
    credentials_params_missing = private_credentials_params.copy()
    password = credentials_params_missing.pop("password")
    private_key = credentials_params_missing.pop("private_key")
    assert password == "letmein"
    assert isinstance(private_key, bytes)
    # Test cert as string
    credentials = SnowflakeCredentials(**private_credentials_params)
    assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_passphrase(
    private_credentials_params,
):
    private_credentials_params[
        "private_key_passphrase"
    ] = private_credentials_params.pop("password")
    credentials_params_missing = private_credentials_params.copy()
    password = credentials_params_missing.pop("private_key_passphrase")
    private_key = credentials_params_missing.pop("private_key")
    assert password == "letmein"
    assert isinstance(private_key, bytes)
    # Test cert as string
    credentials = SnowflakeCredentials(**private_credentials_params)
    assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_path(
    private_credentials_params, tmp_path
):
    private_key_path = tmp_path / "private_key.pem"
    private_key_path.write_bytes(private_credentials_params.pop("private_key"))
    private_credentials_params["private_key_path"] = private_key_path
    private_credentials_params[
        "private_key_passphrase"
    ] = private_credentials_params.pop("password")
    credentials = SnowflakeCredentials(**private_credentials_params)
    assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_invalid(private_credentials_params):
    credentials_params_missing = private_credentials_params.copy()
    private_key = credentials_params_missing.pop("private_key")
    assert isinstance(private_key, bytes)
    assert private_key.startswith(b"----")
    with pytest.raises(ValueError, match="Bad decrypt. Incorrect password?"):
        credentials = SnowflakeCredentials(**private_credentials_params)
        credentials.password = "_wrong_password"
        assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_unexpected_password(
    private_credentials_params,
):
    credentials_params_missing = private_credentials_params.copy()
    private_key = credentials_params_missing.pop("private_key")
    assert isinstance(private_key, bytes)
    assert private_key.startswith(b"----")
    with pytest.raises(
        TypeError, match="Password was not given but private key is encrypted"
    ):
        credentials = SnowflakeCredentials(**private_credentials_params)
        credentials.password = None
        assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_no_pass_password(
    private_no_pass_credentials_params,
):
    credentials_params_missing = private_no_pass_credentials_params.copy()
    password = credentials_params_missing.pop("password")
    private_key = credentials_params_missing.pop("private_key")
    assert password == "letmein"
    assert isinstance(private_key, bytes)
    assert private_key.startswith(b"----")

    with pytest.raises(
        TypeError, match="Password was given but private key is not encrypted"
    ):
        credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
        assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_is_pem(
    private_no_pass_credentials_params,
):
    private_no_pass_credentials_params["private_key"] = "_invalid_key_"
    with pytest.raises(InvalidPemFormat):
        credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
        assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_is_pem_bytes(
    private_no_pass_credentials_params,
):
    private_no_pass_credentials_params["private_key"] = "_invalid_key_"
    with pytest.raises(InvalidPemFormat):
        credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
        assert credentials.resolve_private_key() is not None


def test_snowflake_credentials_validate_private_key_path_init(
    private_key_path_credentials_params,
):
    snowflake_credentials = SnowflakeCredentials(**private_key_path_credentials_params)
    actual_credentials_params = snowflake_credentials.dict()
    for param in private_key_path_credentials_params:
        actual = actual_credentials_params[param]
        expected = private_key_path_credentials_params[param]
        if isinstance(actual, (SecretStr, SecretBytes)):
            actual = actual.get_secret_value()
        elif isinstance(actual, Path):
            actual = relative_path_to_current_platform(actual)
            expected = relative_path_to_current_platform(expected)
        assert actual == expected


def test_get_client(credentials_params, snowflake_connect_mock: MagicMock):
    snowflake_credentials = SnowflakeCredentials(**credentials_params)
    snowflake_credentials.get_client()
    snowflake_connect_mock.assert_called_with(
        application="Prefect_Snowflake_Collection",
        account="account",
        user="user",
        password="password",
    )


def test_get_client_okta_endpoint(
    credentials_params, snowflake_connect_mock: MagicMock
):
    okta_endpoint = "https://account_name.okta.com"
    credentials_params_okta_endpoint = credentials_params.copy()
    del credentials_params_okta_endpoint["password"]
    credentials_params_okta_endpoint["authenticator"] = "okta_endpoint"
    credentials_params_okta_endpoint["endpoint"] = okta_endpoint
    snowflake_credentials = SnowflakeCredentials(**credentials_params_okta_endpoint)
    snowflake_credentials.get_client()
    snowflake_connect_mock.assert_called_with(
        application="Prefect_Snowflake_Collection",
        account="account",
        user="user",
        authenticator="https://account_name.okta.com",
    )


def test_snowflake_credentials_deprecated_okta_endpoint(
    credentials_params, snowflake_connect_mock: MagicMock
):
    okta_endpoint = "https://account_name.okta.com"
    credentials_params_okta_endpoint = credentials_params.copy()
    del credentials_params_okta_endpoint["password"]
    credentials_params_okta_endpoint["authenticator"] = "okta_endpoint"
    credentials_params_okta_endpoint["endpoint"] = okta_endpoint
    snowflake_credentials = SnowflakeCredentials(**credentials_params_okta_endpoint)
    snowflake_credentials.get_client()
    snowflake_connect_mock.assert_called_with(
        application="Prefect_Snowflake_Collection",
        account="account",
        user="user",
        authenticator="https://account_name.okta.com",
    )


def test_snowflake_credentials_unencrypted_private_key_password(
    private_no_pass_credentials_params,
):
    snowflake_credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
    assert snowflake_credentials.private_key is not None
    assert snowflake_credentials.password is not None
    # Raises error if invalid
    with pytest.raises(
        TypeError, match="Password was given but private key is not encrypted"
    ):
        snowflake_credentials.get_client()


def test_snowflake_credentials_unencrypted_private_key_no_password(
    private_no_pass_credentials_params, snowflake_connect_mock: MagicMock
):
    snowflake_credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
    snowflake_credentials.password = None
    assert snowflake_credentials.private_key is not None
    # Raises error if invalid
    snowflake_credentials.get_client()


def test_snowflake_credentials_unencrypted_private_key_empty_password(
    private_no_pass_credentials_params, snowflake_connect_mock: MagicMock
):
    snowflake_credentials = SnowflakeCredentials(**private_no_pass_credentials_params)
    assert snowflake_credentials.private_key is not None

    snowflake_credentials.password = SecretBytes(b" ")
    snowflake_credentials.get_client()
    snowflake_credentials.password = SecretBytes(b"")
    snowflake_credentials.get_client()
    snowflake_credentials.password = SecretStr("")
    snowflake_credentials.get_client()
    snowflake_credentials.password = SecretStr("   ")
    snowflake_credentials.get_client()


def test_snowflake_credentials_encrypted_private_key_is_valid(
    private_credentials_params, snowflake_connect_mock: MagicMock
):
    snowflake_credentials = SnowflakeCredentials(**private_credentials_params)
    assert snowflake_credentials.private_key is not None
    assert snowflake_credentials.password is not None
    # Raises error if invalid
    snowflake_credentials.get_client()


def test_snowflake_with_no_private_key_flow():
    """
    https://github.com/PrefectHQ/prefect-snowflake/issues/62
    """

    @flow
    def snowflake_query_flow():
        snowflake_credentials = SnowflakeCredentials(
            account="account", user="user", password="password", role="MY_ROLE"
        )
        snowflake_connector = SnowflakeConnector(
            database="database",
            warehouse="warehouse",
            schema="schema",
            credentials=snowflake_credentials,
        )
        return snowflake_connector

    snowflake_connector = snowflake_query_flow()
    assert isinstance(snowflake_connector, SnowflakeConnector)
    assert isinstance(snowflake_connector.credentials, SnowflakeCredentials)
    assert snowflake_connector.credentials.private_key is None
    assert snowflake_connector.credentials.private_key_path is None
    assert snowflake_connector.credentials.private_key_passphrase is None
    assert snowflake_connector.credentials.password.get_secret_value() == "password"


def test_snowflake_with_private_key_path_flow():
    """
    https://github.com/PrefectHQ/prefect-snowflake/issues/62
    """

    @flow
    def snowflake_query_flow():
        snowflake_credentials = SnowflakeCredentials(
            account="account",
            user="user",
            private_key_path="private_key_path",
            private_key_passphrase="passphrase",
        )
        snowflake_connector = SnowflakeConnector(
            database="database",
            warehouse="warehouse",
            schema="schema",
            credentials=snowflake_credentials,
        )
        return snowflake_connector

    snowflake_connector = snowflake_query_flow()
    assert isinstance(snowflake_connector, SnowflakeConnector)
    assert isinstance(snowflake_connector.credentials, SnowflakeCredentials)
    assert snowflake_connector.credentials.private_key is None
    assert snowflake_connector.credentials.private_key_path == Path("private_key_path")
    assert (
        snowflake_connector.credentials.private_key_passphrase.get_secret_value()
        == "passphrase"
    )
    assert snowflake_connector.credentials.password is None


def test_snowflake_connect_params(credentials_params, snowflake_connect_mock):
    snowflake_credentials = SnowflakeCredentials(**credentials_params)

    # The returned client is mocked, use the fixture instead
    _ = snowflake_credentials.get_client(autocommit=False)

    assert snowflake_connect_mock.call_args_list[0][1]["autocommit"] is False
