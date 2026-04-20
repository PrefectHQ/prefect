"""
API command — native cyclopts implementation.

Make direct requests to the Prefect API.
"""

import json
import sys
from typing import Annotated, Any, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)

api_app: cyclopts.App = cyclopts.App(
    name="api",
    help="Interact with the Prefect API.",
    version_flags=[],
    help_flags=["--help"],
)


def _parse_headers(header_list: list[str]) -> dict[str, str]:
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


def _parse_data(data: str | None) -> dict[str, Any] | str | None:
    """Parse data input - can be JSON string, @filename, or None."""
    from pathlib import Path

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


def _read_stdin_data() -> dict[str, Any] | None:
    """Read and parse JSON data from stdin if available."""
    if not sys.stdin.isatty():
        try:
            content = sys.stdin.read()
            if content.strip():
                return json.loads(content)
        except json.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON from stdin: {e}")
    return None


def _format_output(response: Any, verbose: bool) -> None:
    """Format and print the response using rich."""
    from rich.syntax import Syntax

    if verbose:
        req = response.request
        _cli.console.print(f"[dim]> {req.method} {req.url}[/dim]")
        for key, value in req.headers.items():
            if key.lower() == "authorization":
                value = "Bearer ***"
            _cli.console.print(f"[dim]> {key}: {value}[/dim]")
        _cli.console.print()

        _cli.console.print(
            f"[dim]< {response.status_code} {response.reason_phrase}[/dim]"
        )
        for key, value in response.headers.items():
            _cli.console.print(f"[dim]< {key}: {value}[/dim]")
        _cli.console.print()

    if response.text:
        try:
            data = response.json()
            json_str = json.dumps(data, indent=2)
            if sys.stdout.isatty():
                syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
                _cli.console.print(syntax)
            else:
                print(json.dumps(data))
        except (json.JSONDecodeError, ValueError):
            _cli.console.print(response.text)


def _get_exit_code(error: Exception) -> int:
    """Determine the appropriate exit code for an error."""
    import httpx

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


@api_app.default
@with_cli_exception_handling
async def api_request(
    method: str,
    path: str,
    *,
    data: Annotated[
        Optional[str],
        cyclopts.Parameter("--data", help="Request body as JSON string or @filename"),
    ] = None,
    headers: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "-H", alias="--header", help="Custom header in 'Key: Value' format"
        ),
    ] = None,
    verbose: Annotated[
        bool,
        cyclopts.Parameter(
            "-v", alias="--verbose", help="Show request/response headers"
        ),
    ] = False,
    root: Annotated[
        bool,
        cyclopts.Parameter("--root", help="Access API root level (e.g., /api/me)"),
    ] = False,
    account: Annotated[
        bool,
        cyclopts.Parameter("--account", help="Access account level (Cloud only)"),
    ] = False,
):
    """Make a direct request to the Prefect API."""
    import httpx
    from rich.console import Console
    from rich.syntax import Syntax

    from prefect.client.cloud import get_cloud_client
    from prefect.client.orchestration import get_client
    from prefect.settings import get_current_settings

    if headers is None:
        headers = []

    console_err = Console(stderr=True)

    http_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    http_method = method.upper()

    if http_method not in http_methods:
        exit_with_error(
            f"Invalid HTTP method: {method!r}. "
            f"Must be one of: {', '.join(sorted(http_methods))}"
        )

    settings = get_current_settings()
    configured_api_url = settings.api.url
    if not configured_api_url:
        exit_with_error(
            "No API URL configured. Set PREFECT_API_URL or run 'prefect cloud login'."
        )

    cloud_api_url = settings.cloud.api_url
    is_cloud = cloud_api_url and configured_api_url.startswith(cloud_api_url)

    if (root or account) and not is_cloud:
        exit_with_error(
            "--root and --account flags are only valid for Prefect Cloud. "
            "For self-hosted servers, paths are relative to your configured API URL."
        )

    body_data = _parse_data(data)

    if body_data is None and data is None:
        stdin_data = _read_stdin_data()
        if stdin_data is not None:
            body_data = stdin_data
        elif http_method in ("POST", "PUT", "PATCH"):
            body_data = {}

    custom_headers = _parse_headers(headers)

    try:
        if root or account:
            async with get_cloud_client() as client:
                if account:
                    route = f"{client.account_base_url}{path}"
                else:
                    route = path

                response = await client.raw_request(
                    http_method,
                    route,
                    json=body_data if body_data is not None else None,
                    headers=custom_headers if custom_headers else None,
                )
                response.raise_for_status()
        else:
            async with get_client() as client:
                response = await client.request(
                    http_method,
                    path,
                    json=body_data if body_data is not None else None,
                    headers=custom_headers if custom_headers else None,
                )
                response.raise_for_status()

        _format_output(response, verbose)

    except httpx.HTTPStatusError as e:
        if verbose:
            _format_output(e.response, verbose)
        else:
            console_err.print(
                f"[red]Error: {e.response.status_code} {e.response.reason_phrase}[/red]"
            )
            if e.response.text:
                try:
                    error_data = e.response.json()
                    json_str = json.dumps(error_data, indent=2)
                    syntax = Syntax(json_str, "json", theme="monokai")
                    console_err.print(syntax)
                except (json.JSONDecodeError, ValueError):
                    console_err.print(e.response.text)

            if e.response.status_code == 401:
                console_err.print(
                    "\n[yellow]Check your API key configuration with:[/yellow] prefect config view"
                )

        raise SystemExit(_get_exit_code(e))

    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        console_err.print(f"[red]Error: Network error - {e}[/red]")
        console_err.print(f"\nCould not connect to API at: {configured_api_url}")
        raise SystemExit(7)

    except Exception as e:
        console_err.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
