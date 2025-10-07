import ssl
import warnings
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from prefect._internal.websockets import (
    create_ssl_context_for_websocket,
    websocket_connect,
)
from prefect.events.clients import events_in_socket_from_api_url
from prefect.settings import (
    PREFECT_API_SSL_CERT_FILE,
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_CLIENT_CUSTOM_HEADERS,
    temporary_settings,
)


def _call_kwargs(mock_connect: MagicMock) -> Dict[str, Any]:
    assert mock_connect.call_count == 1
    _, kwargs = mock_connect.call_args
    return kwargs


def test_websocket_connect_factory() -> None:
    sentinel = object()

    with patch(
        "prefect._internal.websockets.connect", return_value=sentinel
    ) as mock_connect:
        result = websocket_connect("wss://example.com")

    assert result is sentinel
    assert mock_connect.call_count == 1


def test_websocket_connect_adds_ssl_context_for_wss() -> None:
    with patch("prefect._internal.websockets.connect") as mock_connect:
        websocket_connect("wss://example.com")

    kwargs = _call_kwargs(mock_connect)
    assert "ssl" in kwargs
    assert isinstance(kwargs["ssl"], ssl.SSLContext)


def test_websocket_connect_does_not_override_provided_ssl() -> None:
    custom_ssl = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    with patch("prefect._internal.websockets.connect") as mock_connect:
        websocket_connect("wss://example.com", ssl=custom_ssl)

    kwargs = _call_kwargs(mock_connect)
    assert kwargs["ssl"] is custom_ssl


def test_websocket_connect_does_not_add_ssl_for_ws() -> None:
    with patch("prefect._internal.websockets.connect") as mock_connect:
        websocket_connect("ws://example.com")

    kwargs = _call_kwargs(mock_connect)
    assert "ssl" not in kwargs


def test_create_ssl_context_for_websocket_ws_scheme() -> None:
    assert create_ssl_context_for_websocket("ws://example.com") is None


def test_create_ssl_context_for_websocket_wss_insecure() -> None:
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}):
        ssl_context = create_ssl_context_for_websocket("wss://example.com")

    assert ssl_context is not None
    assert not ssl_context.check_hostname
    assert ssl_context.verify_mode == ssl.CERT_NONE


def test_create_ssl_context_for_websocket_wss_secure() -> None:
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: False}):
        ssl_context = create_ssl_context_for_websocket("wss://example.com")

    assert ssl_context is not None
    assert ssl_context.check_hostname is True
    assert ssl_context.verify_mode == ssl.CERT_REQUIRED


def test_create_ssl_context_with_custom_cert_file() -> None:
    with temporary_settings({PREFECT_API_SSL_CERT_FILE: "/custom/cert.pem"}):
        with patch("ssl.create_default_context") as mock_ssl_context:
            create_ssl_context_for_websocket("wss://example.com")

    mock_ssl_context.assert_called_once_with(cafile="/custom/cert.pem")


def test_websocket_custom_headers() -> None:
    custom_headers = {"X-Custom-Header": "test-value", "Authorization": "Bearer token"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        with patch("prefect._internal.websockets.connect") as mock_connect:
            websocket_connect("wss://example.com")

    kwargs = _call_kwargs(mock_connect)
    assert "additional_headers" in kwargs
    additional_headers = kwargs["additional_headers"]
    assert additional_headers["X-Custom-Header"] == "test-value"
    assert additional_headers["Authorization"] == "Bearer token"


def test_websocket_custom_headers_merge_with_existing() -> None:
    custom_headers = {"X-Custom-Header": "test-value"}
    existing_headers = {"X-Existing-Header": "existing-value"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        with patch("prefect._internal.websockets.connect") as mock_connect:
            websocket_connect("wss://example.com", additional_headers=existing_headers)

    kwargs = _call_kwargs(mock_connect)
    additional_headers = kwargs["additional_headers"]
    assert additional_headers["X-Custom-Header"] == "test-value"
    assert additional_headers["X-Existing-Header"] == "existing-value"


def test_websocket_custom_headers_protected_headers_warning() -> None:
    custom_headers = {
        "User-Agent": "custom-agent",
        "Sec-WebSocket-Key": "custom-key",
        "X-Custom-Header": "test-value",
    }

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with patch("prefect._internal.websockets.connect") as mock_connect:
                websocket_connect("wss://example.com")

    assert len(caught) == 2
    messages = {str(warning.message) for warning in caught}
    assert any("Custom header 'User-Agent'" in message for message in messages)
    assert any("Custom header 'Sec-WebSocket-Key'" in message for message in messages)

    kwargs = _call_kwargs(mock_connect)
    additional_headers = kwargs["additional_headers"]
    assert additional_headers["X-Custom-Header"] == "test-value"
    assert "User-Agent" not in additional_headers
    assert "Sec-WebSocket-Key" not in additional_headers


def test_websocket_custom_headers_empty_settings() -> None:
    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: {}}):
        with patch("prefect._internal.websockets.connect") as mock_connect:
            websocket_connect("wss://example.com")

    kwargs = _call_kwargs(mock_connect)
    assert "additional_headers" not in kwargs


async def test_websocket_custom_headers_with_websocket_connect(
    hosted_api_server: str,
) -> None:
    captured_kwargs: Dict[str, Any] = {}
    original_connect = websocket_connect.__globals__["connect"]

    def capturing_connect(*args: Any, **kwargs: Any):
        captured_kwargs.update(kwargs)
        return original_connect(*args, **kwargs)

    custom_headers = {"X-Custom-Header": "test-value"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        with patch("prefect._internal.websockets.connect", new=capturing_connect):
            connector = websocket_connect(
                events_in_socket_from_api_url(hosted_api_server)
            )
            async with connector as websocket:
                pong = await websocket.ping()
                await pong

    assert "additional_headers" in captured_kwargs
    assert captured_kwargs["additional_headers"]["X-Custom-Header"] == "test-value"
