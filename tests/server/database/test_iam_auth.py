
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock boto3 before importing anything that might use it
mock_boto3 = MagicMock()
sys.modules["boto3"] = mock_boto3

import pytest
from unittest.mock import patch
from prefect.server.database.configurations import AsyncPostgresConfiguration
from prefect.settings import PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_IAM_ENABLED, PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_IAM_REGION_NAME, PREFECT_API_DATABASE_CONNECTION_URL, temporary_settings

@pytest.mark.asyncio
async def test_iam_auth_configuration_default_region():
    with temporary_settings({
        PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_IAM_ENABLED: True,
        PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user:pass@host:5432/db"
    }):
        config = AsyncPostgresConfiguration(connection_url="postgresql+asyncpg://user:pass@host:5432/db")
        
        with patch("prefect.server.database.configurations.create_async_engine") as mock_create_engine:
            # Configure mock engine to be awaitable for dispose
            mock_engine = MagicMock()
            mock_engine.dispose = AsyncMock()
            mock_create_engine.return_value = mock_engine

            with patch("prefect.server.database.configurations.TRACKER") as mock_tracker:
                with patch("prefect.server.database.configurations.logfire") as mock_logfire:
                    mock_tracker.active = False
                    
                    # Configure the mock boto3
                    mock_session = MagicMock()
                    mock_boto3.Session.return_value = mock_session
                    mock_client = MagicMock()
                    mock_session.client.return_value = mock_client
                    mock_client.generate_db_auth_token.return_value = "iam-token"
                    mock_session.region_name = "us-east-1"

                    await config.engine()
                    
                    assert mock_create_engine.called
                    call_args = mock_create_engine.call_args
                    connect_args = call_args.kwargs.get("connect_args")
                    assert connect_args is not None
                    assert "password" in connect_args
                    assert callable(connect_args["password"])
                    
                    # Test the password callable
                    password_callable = connect_args["password"]
                    token = await password_callable()
                    assert token == "iam-token"
                    
                    mock_boto3.Session.assert_called()
                    mock_session.client.assert_called_with("rds")
                    mock_client.generate_db_auth_token.assert_called_with(
                        DBHostname="host",
                        Port=5432,
                        DBUsername="user",
                        Region="us-east-1"
                    )

@pytest.mark.asyncio
async def test_iam_auth_configuration_custom_region():
    with temporary_settings({
        PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_IAM_ENABLED: True,
        PREFECT_SERVER_DATABASE_SQLALCHEMY_CONNECT_ARGS_IAM_REGION_NAME: "eu-west-1",
        PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://user:pass@host:5432/db"
    }):
        # Clear engine cache to force recreation
        from prefect.server.database.configurations import ENGINES
        ENGINES.clear()
        
        config = AsyncPostgresConfiguration(connection_url="postgresql+asyncpg://user:pass@host:5432/db")
        
        with patch("prefect.server.database.configurations.create_async_engine") as mock_create_engine:
            # Configure mock engine to be awaitable for dispose
            mock_engine = MagicMock()
            mock_engine.dispose = AsyncMock()
            mock_create_engine.return_value = mock_engine

            with patch("prefect.server.database.configurations.TRACKER") as mock_tracker:
                with patch("prefect.server.database.configurations.logfire") as mock_logfire:
                    mock_tracker.active = False
                    
                    # Configure the mock boto3
                    mock_session = MagicMock()
                    mock_boto3.Session.return_value = mock_session
                    mock_client = MagicMock()
                    mock_session.client.return_value = mock_client
                    mock_client.generate_db_auth_token.return_value = "iam-token-eu"
                    mock_session.region_name = "us-east-1" # Default is different

                    await config.engine()
                    
                    call_args = mock_create_engine.call_args
                    connect_args = call_args.kwargs.get("connect_args")
                    password_callable = connect_args["password"]
                    token = await password_callable()
                    
                    mock_client.generate_db_auth_token.assert_called_with(
                        DBHostname="host",
                        Port=5432,
                        DBUsername="user",
                        Region="eu-west-1"
                    )
