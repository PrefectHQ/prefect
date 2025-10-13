import ssl
import warnings
from unittest.mock import patch

from websockets.asyncio.client import connect

from prefect._internal.websockets import (
    create_ssl_context_for_websocket,
    websocket_connect,
)
from prefect.events.clients import events_in_socket_from_api_url
from prefect.settings import (
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_CLIENT_CUSTOM_HEADERS,
    temporary_settings,
)


def test_websocket_connect_factory():
    """Test that websocket_connect returns a connect instance"""
    connector = websocket_connect("wss://example.com")
    assert isinstance(connector, connect)


def test_create_ssl_context_for_websocket_ws_scheme():
    """Test SSL context creation returns None for ws:// URLs"""
    ssl_context = create_ssl_context_for_websocket("ws://example.com")
    assert ssl_context is None


def test_create_ssl_context_for_websocket_wss_insecure():
    """Test SSL context creation for insecure connections"""
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}):
        ssl_context = create_ssl_context_for_websocket("wss://example.com")
        assert ssl_context is not None
        assert not ssl_context.check_hostname
        assert ssl_context.verify_mode == ssl.CERT_NONE


def test_create_ssl_context_for_websocket_wss_secure():
    """Test SSL context creation for secure connections"""
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: False}):
        ssl_context = create_ssl_context_for_websocket("wss://example.com")
        assert ssl_context is not None
        assert ssl_context.check_hostname is True
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED


def test_websocket_connect_ssl_integration():
    """Test that websocket_connect integrates with SSL context creation"""
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}):
        connector = websocket_connect("wss://example.com")
        assert isinstance(connector, connect)
        # Verify SSL context is configured
        assert "ssl" in connector.connection_kwargs
        ssl_context = connector.connection_kwargs["ssl"]
        assert not ssl_context.check_hostname
        assert ssl_context.verify_mode == ssl.CERT_NONE


def test_websocket_connect_no_ssl_for_ws():
    """Test that websocket_connect doesn't add SSL for ws:// URLs"""
    connector = websocket_connect("ws://example.com")
    assert isinstance(connector, connect)
    # Verify SSL is not configured for ws:// URLs
    assert "ssl" not in connector.connection_kwargs


def test_websocket_connect_kwargs_preservation():
    """Test that additional kwargs are preserved"""
    additional_headers = {"Authorization": "Bearer token"}
    connector = websocket_connect(
        "wss://example.com", additional_headers=additional_headers
    )
    assert isinstance(connector, connect)
    # Verify headers are preserved
    assert connector.additional_headers == additional_headers


def test_create_ssl_context_with_custom_cert_file():
    """Test SSL context creation with custom certificate file"""
    from prefect.settings import PREFECT_API_SSL_CERT_FILE

    with temporary_settings(
        {
            PREFECT_API_TLS_INSECURE_SKIP_VERIFY: False,
            PREFECT_API_SSL_CERT_FILE: "/custom/cert.pem",
        }
    ):
        with patch("ssl.create_default_context") as mock_ssl_context:
            create_ssl_context_for_websocket("wss://example.com")
            mock_ssl_context.assert_called_once_with(cafile="/custom/cert.pem")


def test_websocket_custom_headers():
    """Test that custom headers from settings are added to additional_headers"""
    custom_headers = {"X-Custom-Header": "test-value", "Authorization": "Bearer token"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        connector = websocket_connect("wss://example.com")
        assert isinstance(connector, connect)
        # Verify custom headers are added
        assert connector.additional_headers["X-Custom-Header"] == "test-value"
        assert connector.additional_headers["Authorization"] == "Bearer token"


def test_websocket_custom_headers_merge_with_existing():
    """Test that custom headers merge with existing additional_headers"""

    custom_headers = {"X-Custom-Header": "test-value"}
    existing_headers = {"X-Existing-Header": "existing-value"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        connector = websocket_connect(
            "wss://example.com", additional_headers=existing_headers
        )
        assert isinstance(connector, connect)
        # Verify both custom and existing headers are present
        assert connector.additional_headers["X-Custom-Header"] == "test-value"
        assert connector.additional_headers["X-Existing-Header"] == "existing-value"


def test_websocket_custom_headers_protected_headers_warning():
    """Test that protected headers generate warnings and are ignored"""

    custom_headers = {
        "User-Agent": "custom-agent",
        "Sec-WebSocket-Key": "custom-key",
        "X-Custom-Header": "test-value",
    }

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            connector = websocket_connect("wss://example.com")

            # Should have warnings for protected headers
            assert len(w) == 2
            assert "User-Agent" in str(w[0].message)
            assert "Sec-WebSocket-Key" in str(w[1].message)
            assert "protected WebSocket header" in str(w[0].message)

            # Verify only non-protected headers are in additional_headers
            assert connector.additional_headers["X-Custom-Header"] == "test-value"
            assert "User-Agent" not in connector.additional_headers
            assert "Sec-WebSocket-Key" not in connector.additional_headers


def test_websocket_custom_headers_empty_settings():
    """Test that empty custom headers don't cause issues"""

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: {}}):
        connector = websocket_connect("wss://example.com")
        assert isinstance(connector, connect)
        # Verify no additional headers when settings are empty (should be None or empty dict)
        assert (
            connector.additional_headers is None or connector.additional_headers == {}
        )


async def test_websocket_custom_headers_with_websocket_connect(hosted_api_server: str):
    """Test that custom headers work with the websocket_connect utility function"""

    custom_headers = {"X-Custom-Header": "test-value"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        connector = websocket_connect(events_in_socket_from_api_url(hosted_api_server))
        # Make sure we can connect to the websocket successfully with the custom headers
        async with connector as websocket:
            pong = await websocket.ping()
            await pong
            # If we get here, the connection worked with custom headers
