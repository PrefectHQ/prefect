from unittest.mock import Mock

from prefect.utilities.proxy import WebsocketProxyConnect


def test_init_ws_without_proxy():
    client = WebsocketProxyConnect("ws://example.com")
    assert client.uri == "ws://example.com"
    assert client._WebsocketProxyConnect__host == "example.com"
    assert client._WebsocketProxyConnect__port == 80
    assert client._WebsocketProxyConnect__proxy is None


def test_init_wss_without_proxy():
    client = WebsocketProxyConnect("wss://example.com")
    assert client.uri == "wss://example.com"
    assert client._WebsocketProxyConnect__host == "example.com"
    assert client._WebsocketProxyConnect__port == 443
    assert "server_hostname" in client._WebsocketProxyConnect__kwargs
    assert client._WebsocketProxyConnect__proxy is None


def test_init_ws_with_proxy(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
    mock_proxy = Mock()
    monkeypatch.setattr("prefect.utilities.proxy.Proxy", mock_proxy)

    client = WebsocketProxyConnect("ws://example.com")

    mock_proxy.from_url.assert_called_once_with("http://proxy:3128")
    assert client._WebsocketProxyConnect__proxy is not None


def test_init_wss_with_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "https://proxy:3128")
    mock_proxy = Mock()
    monkeypatch.setattr("prefect.utilities.proxy.Proxy", mock_proxy)

    client = WebsocketProxyConnect("wss://example.com")

    mock_proxy.from_url.assert_called_once_with("https://proxy:3128")
    assert client._WebsocketProxyConnect__proxy is not None
