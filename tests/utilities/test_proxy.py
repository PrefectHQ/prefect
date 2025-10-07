from unittest.mock import patch

import pytest

from prefect._internal.websockets import websocket_connect


@pytest.mark.parametrize("uri", ["ws://example.com", "wss://example.com"])
def test_websocket_connect_leaves_proxy_decision_to_websockets(
    monkeypatch, uri: str
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://secure-proxy:3128")

    with patch("prefect._internal.websockets.connect") as mock_connect:
        websocket_connect(uri)

    assert mock_connect.call_count == 1
    _, kwargs = mock_connect.call_args
    assert "proxy" not in kwargs


def test_websocket_connect_honors_explicit_proxy_kwarg() -> None:
    with patch("prefect._internal.websockets.connect") as mock_connect:
        websocket_connect("wss://example.com", proxy="http://proxy:3128")

    _, kwargs = mock_connect.call_args
    assert kwargs["proxy"] == "http://proxy:3128"
