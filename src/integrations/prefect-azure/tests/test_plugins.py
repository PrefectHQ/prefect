import ssl
from unittest.mock import AsyncMock, MagicMock

import pytest
from prefect_azure.plugins import set_database_connection_params

OSSRDBMS_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


@pytest.fixture
def mock_mi_disabled(monkeypatch):
    """Mock AzureSettings with managed-identity auth disabled."""
    mock_settings = MagicMock()
    mock_settings.postgres.managed_identity.enabled = False
    monkeypatch.setattr("prefect_azure.plugins.AzureSettings", lambda: mock_settings)
    return mock_settings


@pytest.fixture
def mock_mi_enabled(monkeypatch):
    """Mock AzureSettings with managed-identity auth enabled."""
    mock_settings = MagicMock()
    mock_settings.postgres.managed_identity.enabled = True
    mock_settings.postgres.managed_identity.client_id = None
    monkeypatch.setattr("prefect_azure.plugins.AzureSettings", lambda: mock_settings)
    return mock_settings


@pytest.fixture
def mock_credential(monkeypatch):
    """Mock DefaultAzureCredential with an async get_token returning a token."""
    token = MagicMock()
    token.token = "fake-token"
    credential = MagicMock()
    credential.get_token = AsyncMock(return_value=token)
    factory = MagicMock(return_value=credential)
    monkeypatch.setattr("prefect_azure.plugins.DefaultAzureCredential", factory)
    return factory, credential


def test_set_database_connection_params_disabled(mock_mi_disabled):
    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://user@localhost/db",
        settings=None,
    )
    assert params == {}


def test_set_database_connection_params_enabled(mock_mi_enabled, mock_credential):
    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://user@localhost:5432/db",
        settings=None,
    )

    assert "ssl" in params
    assert "password" in params
    assert callable(params["password"])

    # Managed-identity auth requires SSL with secure defaults.
    ssl_ctx = params["ssl"]
    assert ssl_ctx.check_hostname is True
    assert ssl_ctx.verify_mode == ssl.CERT_REQUIRED


async def test_password_callable_returns_token(mock_mi_enabled, mock_credential):
    _factory, credential = mock_credential

    params = set_database_connection_params(
        connection_url="postgresql+asyncpg://user@myhost:5432/mydb",
        settings=None,
    )

    token = await params["password"]()
    assert token == "fake-token"
    credential.get_token.assert_awaited_with(OSSRDBMS_SCOPE)


async def test_client_id_forwarded_to_credential(monkeypatch, mock_credential):
    factory, _credential = mock_credential

    mock_settings = MagicMock()
    mock_settings.postgres.managed_identity.enabled = True
    mock_settings.postgres.managed_identity.client_id = "user-assigned-client-id"
    monkeypatch.setattr("prefect_azure.plugins.AzureSettings", lambda: mock_settings)

    set_database_connection_params(
        connection_url="postgresql+asyncpg://user@host/db",
        settings=None,
    )

    factory.assert_called_once_with(
        managed_identity_client_id="user-assigned-client-id"
    )
