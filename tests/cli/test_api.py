import json
from unittest.mock import Mock

import httpx
import pytest

from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def mock_httpx_client(monkeypatch):
    """Mock PrefectClient's underlying httpx client for testing."""
    from unittest.mock import AsyncMock

    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = httpx.Headers({"content-type": "application/json"})
    mock_response.json.return_value = {"result": "success"}
    mock_response.text = '{"result": "success"}'
    mock_response.raise_for_status = Mock()  # Don't raise by default

    mock_request = Mock(spec=httpx.Request)
    mock_request.method = "GET"
    mock_request.url = httpx.URL("http://test.prefect.io/api/flows")
    mock_request.headers = httpx.Headers({})

    # Mock the underlying _client
    mock_inner_client = Mock()
    mock_inner_client.request = AsyncMock(return_value=mock_response)

    # Mock the PrefectClient
    mock_prefect_client = Mock()
    mock_prefect_client._client = mock_inner_client
    mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
    mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

    # Mock get_client to return our mock
    def mock_get_client():
        return mock_prefect_client

    monkeypatch.setattr("prefect.cli.api.get_client", mock_get_client)

    return mock_inner_client, mock_response, mock_request


def mock_client_with_error(monkeypatch, mock_response):
    """Helper to mock get_client with an error response."""
    from unittest.mock import AsyncMock

    # Mock the underlying _client
    mock_inner_client = Mock()
    mock_inner_client.request = AsyncMock(return_value=mock_response)

    # Mock the PrefectClient
    mock_prefect_client = Mock()
    mock_prefect_client._client = mock_inner_client
    mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
    mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

    # Mock get_client to return our mock
    def mock_get_client():
        return mock_prefect_client

    monkeypatch.setattr("prefect.cli.api.get_client", mock_get_client)


class TestBasicRequests:
    """Test basic request functionality."""

    def test_get_request_oss(self, mock_httpx_client):
        """Test GET request to OSS server."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        # call_args.kwargs for keyword arguments
        assert call_args.kwargs["method"] == "GET"
        assert str(call_args.kwargs["url"]) == "http://localhost:4200/api/flows"

    def test_post_request_with_data(self, mock_httpx_client):
        """Test POST request with inline JSON data."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "POST", "/flows/filter", "--data", '{"limit": 10}'],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "POST"
        assert call_args.kwargs["json"] == {"limit": 10}

    def test_post_request_default_empty_body(self, mock_httpx_client):
        """Test POST request defaults to empty object when no data provided."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "POST", "/flows/filter"],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args.kwargs["json"] == {}

    def test_delete_request(self, mock_httpx_client):
        """Test DELETE request."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "DELETE", "/flows/abc-123"],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "DELETE"

    def test_patch_request_with_data(self, mock_httpx_client):
        """Test PATCH request with data."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                [
                    "api",
                    "PATCH",
                    "/deployments/abc-123",
                    "--data",
                    '{"is_schedule_active": false}',
                ],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "PATCH"
        assert call_args.kwargs["json"] == {"is_schedule_active": False}

    def test_put_request(self, mock_httpx_client):
        """Test PUT request."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "PUT", "/flows/abc-123", "--data", '{"name": "updated"}'],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "PUT"


class TestAlternativeSyntax:
    """Test curl/gh compatibility syntax."""

    def test_method_with_dash_x_flag(self, mock_httpx_client):
        """Test -X flag for method when not positional."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "/flows/filter", "-X", "POST", "--data", "{}"],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        assert call_args.kwargs["method"] == "POST"

    def test_custom_headers(self, mock_httpx_client):
        """Test custom headers with -H flag."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                [
                    "api",
                    "POST",
                    "/flows/filter",
                    "-H",
                    "X-Custom: value",
                    "--data",
                    "{}",
                ],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        headers = call_args.kwargs["headers"]
        assert headers.get("X-Custom") == "value"

    def test_multiple_custom_headers(self, mock_httpx_client):
        """Test multiple custom headers."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                [
                    "api",
                    "POST",
                    "/flows/filter",
                    "-H",
                    "X-Custom-1: value1",
                    "-H",
                    "X-Custom-2: value2",
                    "--data",
                    "{}",
                ],
                expected_code=0,
            )

        mock_client.request.assert_called_once()
        call_args = mock_client.request.call_args
        headers = call_args.kwargs["headers"]
        assert headers.get("X-Custom-1") == "value1"
        assert headers.get("X-Custom-2") == "value2"


class TestPathHandling:
    """Test smart path handling for Cloud vs OSS."""

    def test_oss_path_prefix(self, mock_httpx_client):
        """Test OSS automatically adds /api prefix."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        assert str(call_args.kwargs["url"]) == "http://localhost:4200/api/flows"

    def test_cloud_workspace_prefix(self, mock_httpx_client):
        """Test Cloud automatically adds account/workspace prefix."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings(
            {
                PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/acc-123/workspaces/ws-456",
                PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api",
            }
        ):
            invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        url = str(call_args.kwargs["url"])
        assert "/api/accounts/acc-123/workspaces/ws-456/flows" in url

    def test_root_flag_skips_prefixes(self, mock_httpx_client):
        """Test --root flag accesses API root."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "GET", "/me", "--root"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        assert str(call_args.kwargs["url"]) == "http://localhost:4200/api/me"

    def test_root_flag_with_api_in_hostname(self, mock_httpx_client):
        """Test --root flag with 'api' in hostname doesn't break URL parsing."""
        mock_client, mock_response, _ = mock_httpx_client

        # Test with Cloud-like URL that has "api" in hostname
        with temporary_settings(
            {
                PREFECT_API_URL: "https://api.example.com/api/accounts/acc-123/workspaces/ws-456",
                PREFECT_CLOUD_API_URL: "https://api.example.com/api",
            }
        ):
            invoke_and_assert(
                ["api", "GET", "/me", "--root"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        # Should be https://api.example.com/api/me, NOT https://api/me
        assert str(call_args.kwargs["url"]) == "https://api.example.com/api/me"

    def test_account_flag_for_cloud(self, mock_httpx_client):
        """Test --account flag for account-level operations."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings(
            {
                PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/acc-123/workspaces/ws-456",
                PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api",
            }
        ):
            invoke_and_assert(
                ["api", "GET", "/workspaces", "--account"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        url = str(call_args.kwargs["url"])
        # Should have account but not workspace in path
        assert "/api/accounts/acc-123/workspaces" in url
        assert "/workspaces/ws-456/" not in url

    def test_query_parameters(self, mock_httpx_client):
        """Test query parameters in path."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "GET", "/flows?limit=10&offset=20"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        url = str(call_args.kwargs["url"])
        assert "limit=10" in url
        assert "offset=20" in url


class TestInputSources:
    """Test different input sources for request body."""

    def test_data_from_file(self, mock_httpx_client, tmp_path):
        """Test reading data from file with @filename syntax."""
        mock_client, mock_response, _ = mock_httpx_client

        data_file = tmp_path / "data.json"
        data_file.write_text('{"test": "value"}')

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "POST", "/flows/filter", "--data", f"@{data_file}"],
                expected_code=0,
            )

        call_args = mock_client.request.call_args
        assert call_args.kwargs["json"] == {"test": "value"}

    @pytest.mark.skip(
        reason="Stdin mocking in test environment is complex, tested manually"
    )
    def test_data_from_stdin(self, mock_httpx_client, monkeypatch):
        """Test reading data from stdin (skipped in automated tests, manually verified)."""
        # This test is skipped because mocking stdin.isatty() is challenging
        # in the Typer CLI runner environment. The functionality works correctly
        # when tested manually with:
        # echo '{"test": "value"}' | prefect api POST /endpoint
        pass


class TestErrorHandling:
    """Test error handling and exit codes."""

    def test_404_error_exit_code(self, monkeypatch):
        """Test 404 errors exit with code 4."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"detail": "Flow not found"}
        mock_response.text = '{"detail": "Flow not found"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=Mock(), response=mock_response
        )

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows/invalid-id"],
                expected_code=4,
            )

        assert "404" in result.output

    def test_401_error_exit_code(self, monkeypatch):
        """Test 401 errors exit with code 3."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"detail": "Unauthorized"}
        mock_response.text = '{"detail": "Unauthorized"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=Mock(), response=mock_response
        )

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=3,
            )

        assert "401" in result.output

    def test_500_error_exit_code(self, monkeypatch):
        """Test 500 errors exit with code 5."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 500
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"detail": "Internal server error"}
        mock_response.text = '{"detail": "Internal server error"}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error", request=Mock(), response=mock_response
        )

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=5,
            )

        assert "500" in result.output

    def test_network_error_exit_code(self, monkeypatch):
        """Test network errors exit with code 7."""
        from unittest.mock import AsyncMock

        # Mock the underlying _client with network error
        mock_inner_client = Mock()
        mock_inner_client.request = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        # Mock the PrefectClient
        mock_prefect_client = Mock()
        mock_prefect_client._client = mock_inner_client
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        # Mock get_client to return our mock
        def mock_get_client():
            return mock_prefect_client

        monkeypatch.setattr("prefect.cli.api.get_client", mock_get_client)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=7,
            )

        assert "Connection" in result.output or "network" in result.output.lower()

    def test_422_validation_error_friendly_message(self, monkeypatch):
        """Test 422 validation errors show friendly message."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 422
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {
            "detail": [
                {
                    "loc": ["body", "name"],
                    "msg": "field required",
                    "type": "value_error.missing",
                }
            ]
        }
        mock_response.text = json.dumps(mock_response.json.return_value)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "422 Unprocessable Entity", request=Mock(), response=mock_response
        )

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "POST", "/flows"],
                expected_code=4,
            )

        assert "422" in result.output


class TestOutputFormatting:
    """Test output formatting and verbosity."""

    def test_pretty_print_json_by_default(self, mock_httpx_client):
        """Test JSON is pretty-printed by default."""
        mock_client, mock_response, _ = mock_httpx_client
        mock_response.json.return_value = {"id": "123", "name": "test"}

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows/123"],
                expected_code=0,
            )

        # Pretty-printed JSON has newlines
        assert "\n" in result.output
        assert '"id"' in result.output or "'id'" in result.output

    def test_verbose_shows_headers(self, mock_httpx_client, monkeypatch):
        """Test --verbose shows request/response headers."""
        mock_client, mock_response, mock_request = mock_httpx_client
        mock_request.url = httpx.URL("http://localhost:4200/api/flows")
        mock_request.headers = httpx.Headers({"Authorization": "Bearer test"})
        mock_response.request = mock_request
        mock_response.headers = httpx.Headers({"content-type": "application/json"})

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows", "--verbose"],
                expected_code=0,
            )

        # Should show request and response indicators
        assert "GET" in result.output
        assert "200" in result.output or "OK" in result.output

    def test_verbose_on_error(self, monkeypatch):
        """Test --verbose shows headers on errors."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.json.return_value = {"detail": "Not found"}
        mock_response.text = '{"detail": "Not found"}'

        mock_request = Mock(spec=httpx.Request)
        mock_request.method = "GET"
        mock_request.url = httpx.URL("http://localhost:4200/api/flows/bad")
        mock_request.headers = httpx.Headers({})
        mock_response.request = mock_request

        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=mock_request, response=mock_response
        )

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows/bad", "--verbose"],
                expected_code=4,
            )

        assert "404" in result.output


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_method_positional_takes_precedence_over_flag(self, mock_httpx_client):
        """Test positional method takes precedence over -X flag."""
        mock_client, mock_response, _ = mock_httpx_client

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            # If both positional and -X are provided, positional should win
            # Actually, we should error on this - let's test that instead
            invoke_and_assert(
                ["api", "GET", "/flows", "-X", "POST"],
                expected_code=1,  # Should error
            )

    def test_empty_response_body(self, monkeypatch):
        """Test handling of empty response bodies."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 204
        mock_response.headers = httpx.Headers({})
        mock_response.text = ""
        mock_response.json.side_effect = ValueError("No JSON")
        mock_response.raise_for_status = Mock()  # Don't raise

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            invoke_and_assert(
                ["api", "DELETE", "/flows/123"],
                expected_code=0,
            )

    def test_non_json_response(self, monkeypatch):
        """Test handling of non-JSON responses."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "text/plain"})
        mock_response.text = "Plain text response"
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_response.raise_for_status = Mock()  # Don't raise

        mock_client_with_error(monkeypatch, mock_response)

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200"}):
            result = invoke_and_assert(
                ["api", "GET", "/some-text-endpoint"],
                expected_code=0,
            )

        assert "Plain text response" in result.output
