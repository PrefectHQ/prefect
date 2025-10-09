"""
Command line interface for making direct API requests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import httpx
import typer
from rich.console import Console
from rich.syntax import Syntax

from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import get_client
from prefect.settings import get_current_settings

console: Console = Console()
console_err: Console = Console(stderr=True)


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


def parse_data(data: str | None) -> dict[str, Any] | str | None:
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


def read_stdin_data() -> dict[str, Any] | None:
    """Read and parse JSON data from stdin if available."""
    if not sys.stdin.isatty():
        try:
            content = sys.stdin.read()
            if content.strip():
                return json.loads(content)
        except json.JSONDecodeError as e:
            exit_with_error(f"Invalid JSON from stdin: {e}")
    return None


def format_output(response: httpx.Response, verbose: bool) -> None:
    """Format and print the response using rich."""
    if verbose:
        req = response.request
        console.print(f"[dim]> {req.method} {req.url}[/dim]")
        for key, value in req.headers.items():
            if key.lower() == "authorization":
                value = "Bearer ***"
            console.print(f"[dim]> {key}: {value}[/dim]")
        console.print()

        console.print(f"[dim]< {response.status_code} {response.reason_phrase}[/dim]")
        for key, value in response.headers.items():
            console.print(f"[dim]< {key}: {value}[/dim]")
        console.print()

    if response.text:
        try:
            data = response.json()
            json_str = json.dumps(data, indent=2)
            if sys.stdout.isatty():
                syntax = Syntax(json_str, "json", theme="monokai", word_wrap=True)
                console.print(syntax)
            else:
                print(json.dumps(data))
        except (json.JSONDecodeError, ValueError):
            console.print(response.text)


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
    method: str = typer.Argument(
        ..., help="HTTP method (GET, POST, PUT, PATCH, DELETE)"
    ),
    path: str = typer.Argument(..., help="API path (e.g., /flows, /flows/filter)"),
    data: Optional[str] = typer.Option(
        None,
        "--data",
        help="Request body as JSON string or @filename",
    ),
    headers: list[str] = typer.Option(
        None,
        "-H",
        "--header",
        help="Custom header in 'Key: Value' format",
    ),
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help="Show request/response headers",
    ),
    root: bool = typer.Option(
        False,
        "--root",
        help="Access API root level (e.g., /api/me)",
    ),
    account: bool = typer.Option(
        False,
        "--account",
        help="Access account level (Cloud only)",
    ),
):
    """
    Make a direct request to the Prefect API.

    Examples:
        ```bash
        # GET request
        $ prefect api GET /flows/abc-123

        # POST request with data
        $ prefect api POST /flows/filter --data '{"limit": 10}'

        # POST to filter endpoint (defaults to empty object)
        $ prefect api POST /flows/filter

        # Custom headers
        $ prefect api POST /flows/filter -H "X-Custom: value" --data '{}'

        # Verbose output
        $ prefect api GET /flows --verbose

        # Account-level operation (Cloud)
        $ prefect api GET /workspaces --account

        # API root level (Cloud only)
        $ prefect api GET /me --root
        ```
    """
    if headers is None:
        headers = []

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

    body_data = parse_data(data)

    if body_data is None and data is None:
        stdin_data = read_stdin_data()
        if stdin_data is not None:
            body_data = stdin_data
        elif http_method in ("POST", "PUT", "PATCH"):
            body_data = {}

    custom_headers = parse_headers(headers)

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

        format_output(response, verbose)

    except httpx.HTTPStatusError as e:
        if verbose:
            format_output(e.response, verbose)
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

        raise typer.Exit(get_exit_code(e))

    except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
        console_err.print(f"[red]Error: Network error - {e}[/red]")
        console_err.print(f"\nCould not connect to API at: {configured_api_url}")
        raise typer.Exit(7)

    except Exception as e:
        console_err.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
