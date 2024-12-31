from unittest.mock import Mock

import pytest

from prefect.events.clients import WebsocketProxyConnect


def test_init_ws_without_proxy():
    client = WebsocketProxyConnect("ws://example.com")
    assert client.uri == "ws://example.com"
    assert client._host == "example.com"
    assert client._port == 80
    assert client._proxy is None


def test_init_wss_without_proxy():
    client = WebsocketProxyConnect("wss://example.com")
    assert client.uri == "wss://example.com"
    assert client._host == "example.com"
    assert client._port == 443
    assert "server_hostname" in client._kwargs
    assert client._proxy is None


def test_init_ws_with_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
    mock_proxy = Mock()
    monkeypatch.setattr("prefect.events.clients.Proxy", mock_proxy)

    client = WebsocketProxyConnect("ws://example.com")

    mock_proxy.from_url.assert_called_once_with("http://proxy:3128")
    assert client._proxy is not None


def test_init_wss_with_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    mock_proxy = Mock()
    monkeypatch.setattr("prefect.events.clients.Proxy", mock_proxy)

    client = WebsocketProxyConnect("wss://example.com")

    mock_proxy.from_url.assert_called_once_with("http://proxy:3128")
    assert client._proxy is not None


@pytest.mark.parametrize(
    "no_proxy", ["example.com", ".com", "example.com,example2.com"]
)
def test_init_ws_with_no_proxy(monkeypatch, no_proxy: str):
    # Validate http proxy is set
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
    client = WebsocketProxyConnect("ws://example.com")
    assert client._proxy is not None

    # Keeping existing proxy configuration, validate we can disable it with NO_PROXY
    monkeypatch.setenv("NO_PROXY", no_proxy)
    client = WebsocketProxyConnect("ws://example.com")
    assert client._proxy is None


@pytest.mark.parametrize(
    "no_proxy", ["example.com", ".com", "example.com,example2.com"]
)
def test_init_wss_with_no_proxy(monkeypatch, no_proxy: str):
    # Validate https proxy is set
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy:3128")
    client = WebsocketProxyConnect("wss://example.com")
    assert client._proxy is not None

    # Keeping existing proxy configuration, validate we can disable it with NO_PROXY
    monkeypatch.setenv("NO_PROXY", no_proxy)
    client = WebsocketProxyConnect("wss://example.com")
    assert client._proxy is None
