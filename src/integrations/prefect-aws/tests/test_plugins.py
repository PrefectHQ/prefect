from unittest.mock import MagicMock

import pytest
from prefect_aws.plugins import get_database_connection_params


@pytest.fixture
def mock_boto3_session(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr("boto3.Session", MagicMock(return_value=mock_session))
    return mock_session


def test_get_database_connection_params_disabled():
    # Mock settings with disabled IAM
    settings = MagicMock()
    settings.server.database.sqlalchemy.connect_args.iam.enabled = False

    params = get_database_connection_params(
        connection_url="postgresql+asyncpg://user:pass@localhost/db",
        settings=settings,
    )
    assert params == {}


def test_get_database_connection_params_enabled(mock_boto3_session):
    # Mock settings with enabled IAM
    settings = MagicMock()
    settings.server.database.sqlalchemy.connect_args.iam.enabled = True
    settings.server.database.sqlalchemy.connect_args.iam.region_name = "us-west-2"

    params = get_database_connection_params(
        connection_url="postgresql+asyncpg://user:pass@localhost:5432/db",
        settings=settings,
    )

    assert "ssl" in params
    assert "password" in params
    assert callable(params["password"])

    # Verify SSL context
    ssl_ctx = params["ssl"]
    assert ssl_ctx.check_hostname is False
    assert ssl_ctx.verify_mode == 0  # ssl.CERT_NONE


def test_get_database_connection_params_token_generation(mock_boto3_session):
    mock_client = MagicMock()
    mock_boto3_session.client.return_value = mock_client
    mock_client.generate_db_auth_token.return_value = "fake-token"

    settings = MagicMock()
    settings.server.database.sqlalchemy.connect_args.iam.enabled = True
    settings.server.database.sqlalchemy.connect_args.iam.region_name = "us-east-1"

    params = get_database_connection_params(
        connection_url="postgresql+asyncpg://myuser:pass@myhost:5432/mydb",
        settings=settings,
    )

    token = params["password"]()
    assert token == "fake-token"

    mock_boto3_session.client.assert_called_with("rds", region_name="us-east-1")
    mock_client.generate_db_auth_token.assert_called_with(
        DBHostname="myhost",
        Port=5432,
        DBUsername="myuser",
        Region="us-east-1",
    )


def test_get_database_connection_params_defaults_region(mock_boto3_session):
    mock_boto3_session.region_name = "eu-central-1"

    settings = MagicMock()
    settings.server.database.sqlalchemy.connect_args.iam.enabled = True
    settings.server.database.sqlalchemy.connect_args.iam.region_name = None

    params = get_database_connection_params(
        connection_url="postgresql+asyncpg://user:pass@host/db",
        settings=settings,
    )

    params["password"]()

    # Should use session region
    mock_boto3_session.client.assert_called_with("rds", region_name="eu-central-1")
