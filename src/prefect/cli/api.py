"""
Command line interface for making direct API requests.
"""

import json
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import typer
from typing_extensions import Annotated

from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.settings import get_current_settings


def build_api_url(
    path: str,
    api_url: str,
    cloud_api_url: str | None,
    root: bool,
    account: bool,
) -> str:
    """
    Build the full API URL based on configuration and flags.

    Args:
        path: The path to request (e.g., /flows, /flows/filter)
        api_url: The PREFECT_API_URL setting value
        cloud_api_url: The PREFECT_CLOUD_API_URL setting value
        root: If True, use API root level (e.g., /api/me)
        account: If True, use account level (Cloud only)

    Returns:
        The full URL to request
    """
    if not path.startswith("/"):
        path = f"/{path}"

    parsed = urlparse(api_url)
    is_cloud = cloud_api_url and api_url.startswith(cloud_api_url)

    if root:
        new_path = f"/api{path}"
        return urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))

    if is_cloud:
        if account:
            path_parts = parsed.path.split("/")
            if "accounts" in path_parts:
                acc_idx = path_parts.index("accounts")
                if acc_idx + 1 < len(path_parts):
                    account_id = path_parts[acc_idx + 1]
                    new_path = f"/api/accounts/{account_id}{path}"
                    return urlunparse(
                        (parsed.scheme, parsed.netloc, new_path, "", "", "")
                    )
            return urljoin(cloud_api_url + "/", path.lstrip("/"))
        else:
            return urljoin(api_url + "/", path.lstrip("/"))
    else:
        new_path = f"/api{path}"
        return urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))


def parse_headers(header_list: list[str]) -> dict[str, str]:
    """Parse header strings in format 'Key: Value' into a dict."""
    headers = {}
    for header in header_list:
        if ":" not in header:
            exit_with_error(
                f"Invalid header format: {header!r}. Use 'Key: Value' format."
            )
        key, value = header.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def parse_data(data: str | None) -> dict | str | None:
    """Parse data input - can be JSON string, @filename, or None."""
    if data is None:
        return None

    if data.startswith("@"):
        filepath = Path(data[1:])
        if not filepath.exists():
            exit_with_error(f"File not found: {filepath}")
        try:
            content = filepath.read_text()
            return json.loads(content)
        except json.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON in file {filepath}: {e}")
    else:
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON data: {e}")


def read_stdin_data() -> dict | None:
    """Read and parse JSON data from stdin if available."""
    if not sys.stdin.isatty():
        try:
            content = sys.stdin.read()
            if content.strip():
                return json.loads(content)
        except json.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON from stdin: {e}")
    return None


def format_output(response: httpx.Response, verbose: bool) -> str:
    """Format the response for output."""
    output_parts = []

    if verbose:
        req = response.request
        output_parts.append(f"> {req.method} {req.url}")
        for key, value in req.headers.items():
            if key.lower() == "authorization":
                value = "Bearer ***"
            output_parts.append(f"> {key}: {value}")
        output_parts.append("")

        output_parts.append(
            f"< HTTP/1.1 {response.status_code} {response.reason_phrase}"
        )
        for key, value in response.headers.items():
            output_parts.append(f"< {key}: {value}")
        output_parts.append("")

    if response.text:
        try:
            data = response.json()
            if sys.stdout.isatty():
                output_parts.append(json.dumps(data, indent=2))
            else:
                output_parts.append(json.dumps(data))
        except (json.JSONDecodeError, ValueError):
            output_parts.append(response.text)

    return "\n".join(output_parts)


def get_exit_code(error: Exception) -> int:
    """Determine the appropriate exit code for an error."""
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status in (401, 403):
            return 3
        elif 400 <= status < 500:
            return 4
        elif 500 <= status < 600:
            return 5
    elif isinstance(
        error, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)
    ):
        return 7

    return 1


@app.command(name="api")
async def api_request(
    method_or_path: Annotated[
        Optional[str],
        typer.Argument(help="HTTP method (GET, POST, etc.) or path if using -X flag"),
    ] = None,
    path_arg: Annotated[
        Optional[str], typer.Argument(help="API path (e.g., /flows, /flows/filter)")
    ] = None,
    method: Annotated[
        Optional[str],
        typer.Option("-X", "--method", help="HTTP method (alternative to positional)"),
    ] = None,
    data: Annotated[
        Optional[str],
        typer.Option("--data", help="Request body as JSON string or @filename"),
    ] = None,
    headers: Annotated[
        Optional[list[str]],
        typer.Option("-H", "--header", help="Custom header in 'Key: Value' format"),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("-v", "--verbose", help="Show request/response headers")
    ] = False,
    root: Annotated[
        bool, typer.Option("--root", help="Access API root level (e.g., /api/me)")
    ] = False,
    account: Annotated[
        bool, typer.Option("--account", help="Access account level (Cloud only)")
    ] = False,
):
    """
    Make a direct request to the Prefect API.

    Examples:

        # GET request
        $ prefect api GET /flows/abc-123

        # POST request with data
        $ prefect api POST /flows/filter --data '{"limit": 10}'

        # POST to filter endpoint (defaults to empty object)
        $ prefect api POST /flows/filter

        # Using -X flag
        $ prefect api /flows -X GET

        # Custom headers
        $ prefect api POST /flows/filter -H "X-Custom: value" --data '{}'

        # Verbose output
        $ prefect api GET /flows --verbose

        # Account-level operation (Cloud)
        $ prefect api GET /workspaces --account

        # API root level
        $ prefect api GET /me --root
    """
    if method_or_path is None:
        return

    if headers is None:
        headers = []

    http_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}

    if method_or_path.upper() in http_methods:
        if method is not None:
            exit_with_error(
                "Cannot specify method both as positional argument and with -X flag"
            )
        http_method = method_or_path.upper()
        if path_arg is None:
            exit_with_error(
                "Path argument is required when method is specified positionally"
            )
        path = path_arg
    else:
        if method is None:
            exit_with_error(
                f"Method must be specified either as first argument or with -X flag. "
                f"Got {method_or_path!r} which is not a recognized HTTP method."
            )
        http_method = method.upper()
        path = method_or_path
        if path_arg is not None:
            exit_with_error(
                "Too many arguments. When using -X flag, provide only the path."
            )

    settings = get_current_settings()
    api_url = settings.api.url
    if not api_url:
        exit_with_error(
            "No API URL configured. Set PREFECT_API_URL or run 'prefect cloud login'."
        )

    cloud_api_url = settings.cloud.api_url
    api_key = settings.api.key.get_secret_value() if settings.api.key else None

    url = build_api_url(path, api_url, cloud_api_url, root, account)
    body_data = parse_data(data)

    if body_data is None and data is None:
        stdin_data = read_stdin_data()
        if stdin_data is not None:
            body_data = stdin_data
        elif http_method in ("POST", "PUT", "PATCH"):
            body_data = {}

    custom_headers = parse_headers(headers)

    request_headers = {"Accept": "application/json"}
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    if body_data is not None:
        request_headers["Content-Type"] = "application/json"
    request_headers.update(custom_headers)

    try:
        async with get_client() as client:
            response = await client._client.request(
                method=http_method,
                url=url,
                json=body_data if body_data is not None else None,
                headers=request_headers,
            )
            response.raise_for_status()

            output = format_output(response, verbose)
            if output:
                print(output)

    except httpx.HTTPStatusError as e:
        if verbose:
            output = format_output(e.response, verbose)
            print(output, file=sys.stderr)
        else:
            print(
                f"Error: {e.response.status_code} {e.response.reason_phrase}",
                file=sys.stderr,
            )
            if e.response.text:
                try:
                    error_data = e.response.json()
                    print(json.dumps(error_data, indent=2), file=sys.stderr)
                except (json.JSONDecodeError, ValueError):
                    print(e.response.text, file=sys.stderr)

            if e.response.status_code == 401:
                print(
                    "\nCheck your API key configuration with: prefect config view",
                    file=sys.stderr,
                )

        raise typer.Exit(get_exit_code(e))

    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        print(f"Error: Network error - {e}", file=sys.stderr)
        print(f"\nCould not connect to API at: {api_url}", file=sys.stderr)
        raise typer.Exit(7)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(1)
