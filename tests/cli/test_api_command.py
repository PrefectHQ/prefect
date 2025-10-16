import json
from uuid import UUID

import httpx
import pytest
from respx import MockRouter

from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_CLIENT_CSRF_SUPPORT_ENABLED,
    PREFECT_CLOUD_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert


@pytest.fixture
def account_id() -> UUID:
    """Test account ID."""
    return UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def workspace_id() -> UUID:
    """Test workspace ID."""
    return UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture(autouse=True)
def test_settings():
    """Configure settings for testing."""
    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: False,
            PREFECT_CLIENT_CSRF_SUPPORT_ENABLED: False,
        }
    ):
        yield


class TestBasicRequests:
    """Test basic request functionality."""

    def test_get_request_oss(self, respx_mock: MockRouter) -> None:
        """Test GET request to OSS server."""
        respx_mock.get("http://localhost:4200/api/flows").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=0,
            )

    def test_post_request_with_data(self, respx_mock: MockRouter) -> None:
        """Test POST request with inline JSON data."""
        route = respx_mock.post("http://localhost:4200/api/flows/filter").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "POST", "/flows/filter", "--data", '{"limit": 10}'],
                expected_code=0,
            )

        assert route.called
        assert json.loads(route.calls.last.request.content) == {"limit": 10}

    def test_post_request_default_empty_body(self, respx_mock: MockRouter) -> None:
        """Test POST request defaults to empty object when no data provided."""
        route = respx_mock.post("http://localhost:4200/api/flows/filter").mock(
            return_value=httpx.Response(200, json=[])
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "POST", "/flows/filter"],
                expected_code=0,
            )

        assert route.called
        assert json.loads(route.calls.last.request.content) == {}

    def test_delete_request(self, respx_mock: MockRouter) -> None:
        """Test DELETE request."""
        route = respx_mock.delete("http://localhost:4200/api/flows/abc-123").mock(
            return_value=httpx.Response(204)
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "DELETE", "/flows/abc-123"],
                expected_code=0,
            )

        assert route.called

    def test_patch_request_with_data(self, respx_mock: MockRouter) -> None:
        """Test PATCH request with data."""
        route = respx_mock.patch("http://localhost:4200/api/deployments/abc-123").mock(
            return_value=httpx.Response(200, json={"updated": True})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
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

        assert route.called
        assert json.loads(route.calls.last.request.content) == {
            "is_schedule_active": False
        }

    def test_put_request(self, respx_mock: MockRouter) -> None:
        """Test PUT request."""
        route = respx_mock.put("http://localhost:4200/api/flows/abc-123").mock(
            return_value=httpx.Response(200, json={"updated": True})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "PUT", "/flows/abc-123", "--data", '{"name": "updated"}'],
                expected_code=0,
            )

        assert route.called


class TestCustomHeaders:
    """Test custom headers functionality."""

    def test_custom_headers(self, respx_mock: MockRouter) -> None:
        """Test custom headers with -H flag."""
        route = respx_mock.post("http://localhost:4200/api/flows/filter").mock(
            return_value=httpx.Response(200, json={})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
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

        assert route.called
        assert route.calls.last.request.headers.get("X-Custom") == "value"

    def test_multiple_custom_headers(self, respx_mock: MockRouter) -> None:
        """Test multiple custom headers."""
        route = respx_mock.post("http://localhost:4200/api/flows/filter").mock(
            return_value=httpx.Response(200, json={})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
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

        assert route.called
        assert route.calls.last.request.headers.get("X-Custom-1") == "value1"
        assert route.calls.last.request.headers.get("X-Custom-2") == "value2"


class TestPathHandling:
    """Test smart path handling for Cloud vs OSS."""

    def test_oss_uses_api_prefix(self, respx_mock: MockRouter) -> None:
        """Test OSS automatically uses /api prefix from configured URL."""
        route = respx_mock.get("http://localhost:4200/api/flows").mock(
            return_value=httpx.Response(200, json=[])
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=0,
            )

        assert route.called

    def test_cloud_workspace_requests(
        self, respx_mock: MockRouter, account_id: UUID, workspace_id: UUID
    ) -> None:
        """Test Cloud workspace requests use workspace URL."""
        route = respx_mock.get(
            f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}/flows"
        ).mock(return_value=httpx.Response(200, json=[]))

        with temporary_settings(
            {
                PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}",
                PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api",
            }
        ):
            invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=0,
            )

        assert route.called

    def test_root_flag_uses_cloud_api_root(
        self, respx_mock: MockRouter, account_id: UUID, workspace_id: UUID
    ) -> None:
        """Test --root flag uses CloudClient for API root."""
        route = respx_mock.get("https://api.prefect.cloud/api/me").mock(
            return_value=httpx.Response(200, json={"user": "test"})
        )

        with temporary_settings(
            {
                PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}",
                PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api",
            }
        ):
            invoke_and_assert(
                ["api", "GET", "/me", "--root"],
                expected_code=0,
            )

        assert route.called

    def test_root_flag_requires_cloud(self, respx_mock: MockRouter) -> None:
        """Test --root flag requires Cloud."""
        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/me", "--root"],
                expected_code=1,
            )

        assert (
            "--root and --account flags are only valid for Prefect Cloud"
            in result.output
        )

    def test_account_flag_uses_cloud_client(
        self, respx_mock: MockRouter, account_id: UUID, workspace_id: UUID
    ) -> None:
        """Test --account flag uses CloudClient with account path."""
        route = respx_mock.get(
            f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces"
        ).mock(return_value=httpx.Response(200, json=[]))

        with temporary_settings(
            {
                PREFECT_API_URL: f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}",
                PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api",
            }
        ):
            invoke_and_assert(
                ["api", "GET", "/workspaces", "--account"],
                expected_code=0,
            )

        assert route.called

    def test_query_parameters(self, respx_mock: MockRouter) -> None:
        """Test query parameters in path."""
        route = respx_mock.get(
            "http://localhost:4200/api/flows?limit=10&offset=20"
        ).mock(return_value=httpx.Response(200, json=[]))

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "GET", "/flows?limit=10&offset=20"],
                expected_code=0,
            )

        assert route.called


class TestInputSources:
    """Test different input sources for request body."""

    def test_data_from_file(self, respx_mock: MockRouter, tmp_path) -> None:
        """Test reading data from file with @filename syntax."""
        route = respx_mock.post("http://localhost:4200/api/flows/filter").mock(
            return_value=httpx.Response(200, json={})
        )

        data_file = tmp_path / "data.json"
        data_file.write_text('{"test": "value"}')

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "POST", "/flows/filter", "--data", f"@{data_file}"],
                expected_code=0,
            )

        assert route.called
        assert json.loads(route.calls.last.request.content) == {"test": "value"}


class TestErrorHandling:
    """Test error handling and exit codes."""

    def test_404_error_exit_code(self, respx_mock: MockRouter) -> None:
        """Test 404 errors exit with code 4."""
        respx_mock.get("http://localhost:4200/api/flows/invalid-id").mock(
            return_value=httpx.Response(404, json={"detail": "Flow not found"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows/invalid-id"],
                expected_code=4,
            )

        assert "404" in result.output

    def test_401_error_exit_code(self, respx_mock: MockRouter) -> None:
        """Test 401 errors exit with code 3."""
        respx_mock.get("http://localhost:4200/api/flows").mock(
            return_value=httpx.Response(401, json={"detail": "Unauthorized"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=3,
            )

        assert "401" in result.output

    def test_500_error_exit_code(self, respx_mock: MockRouter) -> None:
        """Test 500 errors exit with code 5."""
        respx_mock.get("http://localhost:4200/api/flows").mock(
            return_value=httpx.Response(500, json={"detail": "Internal server error"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows"],
                expected_code=5,
            )

        assert "500" in result.output

    def test_422_validation_error(self, respx_mock: MockRouter) -> None:
        """Test 422 validation errors show friendly message."""
        respx_mock.post("http://localhost:4200/api/flows").mock(
            return_value=httpx.Response(
                422,
                json={
                    "detail": [
                        {
                            "loc": ["body", "name"],
                            "msg": "field required",
                            "type": "value_error.missing",
                        }
                    ]
                },
            )
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "POST", "/flows"],
                expected_code=4,
            )

        assert "422" in result.output


class TestOutputFormatting:
    """Test output formatting and verbosity."""

    def test_json_output(self, respx_mock: MockRouter) -> None:
        """Test JSON is output correctly."""
        respx_mock.get("http://localhost:4200/api/flows/123").mock(
            return_value=httpx.Response(200, json={"id": "123", "name": "test"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows/123"],
                expected_code=0,
            )

        assert "123" in result.output
        assert "test" in result.output

    def test_verbose_shows_request_info(self, respx_mock: MockRouter) -> None:
        """Test --verbose shows request details."""
        respx_mock.get("http://localhost:4200/api/flows").mock(
            return_value=httpx.Response(
                200, json={}, headers={"content-type": "application/json"}
            )
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows", "--verbose"],
                expected_code=0,
            )

        assert "GET" in result.output
        assert "200" in result.output

    def test_verbose_on_error(self, respx_mock: MockRouter) -> None:
        """Test --verbose shows details on errors."""
        respx_mock.get("http://localhost:4200/api/flows/bad").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/flows/bad", "--verbose"],
                expected_code=4,
            )

        assert "404" in result.output


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_invalid_http_method(self, respx_mock: MockRouter) -> None:
        """Test invalid HTTP method shows helpful error."""
        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "INVALID", "/flows"],
                expected_code=1,
            )

        assert "Invalid HTTP method" in result.output

    def test_empty_response_body(self, respx_mock: MockRouter) -> None:
        """Test handling of empty response bodies."""
        respx_mock.delete("http://localhost:4200/api/flows/123").mock(
            return_value=httpx.Response(204)
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            invoke_and_assert(
                ["api", "DELETE", "/flows/123"],
                expected_code=0,
            )

    def test_non_json_response(self, respx_mock: MockRouter) -> None:
        """Test handling of non-JSON responses."""
        respx_mock.get("http://localhost:4200/api/some-text-endpoint").mock(
            return_value=httpx.Response(
                200, text="Plain text response", headers={"content-type": "text/plain"}
            )
        )

        with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
            result = invoke_and_assert(
                ["api", "GET", "/some-text-endpoint"],
                expected_code=0,
            )

        assert "Plain text response" in result.output
