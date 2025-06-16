import os
import ssl
from unittest.mock import patch

import pytest

from prefect._internal.websockets import (
    WebsocketProxyConnect,
    create_ssl_context_for_websocket,
    websocket_connect,
)
from prefect.settings import (
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    temporary_settings,
)


def test_websocket_connect_factory():
    """Test that websocket_connect returns WebsocketProxyConnect instance"""
    connector = websocket_connect("wss://example.com")
    assert isinstance(connector, WebsocketProxyConnect)


def test_websocket_proxy_connect_invalid_uri_raises_value_error():
    """Test that invalid URI schemes raise appropriate errors"""
    with pytest.raises(ValueError, match="Invalid URI"):
        WebsocketProxyConnect("invalid-uri")


def test_websocket_proxy_connect_unsupported_scheme_raises_value_error():
    """Test that unsupported URI schemes raise appropriate errors"""
    with pytest.raises(ValueError, match="Unsupported scheme"):
        WebsocketProxyConnect("ftp://example.com")


def test_websocket_proxy_connect_ws_scheme():
    """Test WebSocket proxy connect with ws:// scheme"""
    connector = WebsocketProxyConnect("ws://example.com")
    assert connector._host == "example.com"
    assert connector._port == 80
    assert connector.uri == "ws://example.com"


def test_websocket_proxy_connect_wss_scheme():
    """Test WebSocket proxy connect with wss:// scheme"""
    connector = WebsocketProxyConnect("wss://example.com")
    assert connector._host == "example.com"
    assert connector._port == 443
    assert connector.uri == "wss://example.com"


def test_websocket_proxy_connect_custom_port():
    """Test WebSocket proxy connect with custom port"""
    connector = WebsocketProxyConnect("wss://example.com:8443")
    assert connector._host == "example.com"
    assert connector._port == 8443


def test_websocket_proxy_connect_with_http_proxy():
    """Test proxy configuration with HTTP_PROXY environment variable"""
    old_proxy = os.environ.get("HTTP_PROXY")
    os.environ["HTTP_PROXY"] = "http://proxy.example.com:8080"

    try:
        connector = WebsocketProxyConnect("ws://example.com")
        assert connector._proxy is not None
    finally:
        if old_proxy:
            os.environ["HTTP_PROXY"] = old_proxy
        elif "HTTP_PROXY" in os.environ:
            del os.environ["HTTP_PROXY"]


def test_websocket_proxy_connect_with_https_proxy():
    """Test proxy configuration with HTTPS_PROXY environment variable"""
    old_proxy = os.environ.get("HTTPS_PROXY")
    os.environ["HTTPS_PROXY"] = "http://proxy.example.com:8080"

    try:
        connector = WebsocketProxyConnect("wss://example.com")
        assert connector._proxy is not None
    finally:
        if old_proxy:
            os.environ["HTTPS_PROXY"] = old_proxy
        elif "HTTPS_PROXY" in os.environ:
            del os.environ["HTTPS_PROXY"]


def test_websocket_proxy_connect_proxy_bypass():
    """Test that proxy bypass logic works correctly"""
    old_proxy = os.environ.get("HTTPS_PROXY")
    os.environ["HTTPS_PROXY"] = "http://proxy.example.com:8080"

    try:
        with patch("prefect._internal.websockets.proxy_bypass", return_value=True):
            connector = WebsocketProxyConnect("wss://example.com")
            assert connector._proxy is None
    finally:
        if old_proxy:
            os.environ["HTTPS_PROXY"] = old_proxy
        elif "HTTPS_PROXY" in os.environ:
            del os.environ["HTTPS_PROXY"]


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


def test_websocket_proxy_connect_ssl_integration():
    """Test that WebsocketProxyConnect integrates with SSL context creation"""
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}):
        connector = WebsocketProxyConnect("wss://example.com")
        # SSL context should be in kwargs
        assert "ssl" in connector._kwargs
        ssl_context = connector._kwargs["ssl"]
        assert not ssl_context.check_hostname
        assert ssl_context.verify_mode == ssl.CERT_NONE


def test_websocket_proxy_connect_no_ssl_for_ws():
    """Test that WebsocketProxyConnect doesn't add SSL for ws:// URLs"""
    connector = WebsocketProxyConnect("ws://example.com")
    assert "ssl" not in connector._kwargs


def test_websocket_proxy_connect_server_hostname():
    """Test that server_hostname is set for wss:// connections"""
    connector = WebsocketProxyConnect("wss://example.com")
    assert "server_hostname" in connector._kwargs
    assert connector._kwargs["server_hostname"] == "example.com"


def test_websocket_proxy_connect_no_server_hostname_for_ws():
    """Test that server_hostname is not set for ws:// connections"""
    connector = WebsocketProxyConnect("ws://example.com")
    assert "server_hostname" not in connector._kwargs


def test_websocket_proxy_connect_kwargs_preservation():
    """Test that additional kwargs are preserved"""
    extra_headers = {"Authorization": "Bearer token"}
    connector = WebsocketProxyConnect("wss://example.com", extra_headers=extra_headers)
    assert connector._kwargs["extra_headers"] == extra_headers


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
