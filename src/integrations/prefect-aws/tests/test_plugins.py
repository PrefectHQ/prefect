import ssl
from unittest.mock import MagicMock

import pytest
from prefect_aws.plugins import set_database_connection_params


@pytest.fixture
def mock_boto3_session(monkeypatch):
    mock_session = MagicMock()
    monkeypatch.setattr("boto3.Session", MagicMock(return_value=mock_session))
    return mock_session


@pytest.fixture
def mock_iam_disabled(monkeypatch):
    """Mock AwsSettings with IAM disabled."""
    mock_settings = MagicMock()
    mock_settings.rds.iam.enabled = False
    monkeypatch.setattr("prefect_aws.plugins.AwsSettings", lambda: mock_settings)
    return mock_settings


@pytest.fixture
def mock_iam_enabled(monkeypatch):
    """Mock AwsSettings with IAM enabled."""
    mock_settings = MagicMock()
    mock_settings.rds.iam.enabled = True
    mock_settings.rds.iam.region_name = "us-west-2"
    monkeypatch.setattr("prefect_aws.plugins.AwsSettings", lambda: mock_settings)
    return mock_settings


def test_set_database_connection_params_disabled(mock_iam_disabled):
    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://user:pass@localhost/db",
        settings=None,  # Not used anymore
    )
    assert params == {}


def test_set_database_connection_params_enabled(mock_boto3_session, mock_iam_enabled):
    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://user:pass@localhost:5432/db",
        settings=None,  # Not used anymore
    )

    assert "ssl" in params
    assert "password" in params
    assert callable(params["password"])

    # Verify SSL context has secure defaults
    ssl_ctx = params["ssl"]
    assert ssl_ctx.check_hostname is True
    assert ssl_ctx.verify_mode == ssl.CERT_REQUIRED


def test_set_database_connection_params_token_generation(
    mock_boto3_session, monkeypatch
):
    mock_client = MagicMock()
    mock_boto3_session.client.return_value = mock_client
    mock_client.generate_db_auth_token.return_value = "fake-token"

    mock_settings = MagicMock()
    mock_settings.rds.iam.enabled = True
    mock_settings.rds.iam.region_name = "us-east-1"
    monkeypatch.setattr("prefect_aws.plugins.AwsSettings", lambda: mock_settings)

    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://myuser:pass@myhost:5432/mydb",
        settings=None,
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


def test_set_database_connection_params_defaults_region(
    mock_boto3_session, monkeypatch
):
    mock_boto3_session.region_name = "eu-central-1"

    mock_settings = MagicMock()
    mock_settings.rds.iam.enabled = True
    mock_settings.rds.iam.region_name = None
    monkeypatch.setattr("prefect_aws.plugins.AwsSettings", lambda: mock_settings)

    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://user:pass@host/db",
        settings=None,
    )

    params["password"]()

    # Should use session region
    mock_boto3_session.client.assert_called_with("rds", region_name="eu-central-1")
