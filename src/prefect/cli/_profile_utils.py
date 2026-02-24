"""
Shared utilities for profile connection checking.

Extracted from prefect.cli.profile so both typer and cyclopts
command modules can import without pulling in CLI framework deps.
"""

from __future__ import annotations

import httpx

from prefect.client.base import determine_server_type
from prefect.client.orchestration import ServerType, get_client
from prefect.utilities.collections import AutoEnum


class ConnectionStatus(AutoEnum):
    CLOUD_CONNECTED = AutoEnum.auto()
    CLOUD_ERROR = AutoEnum.auto()
    CLOUD_UNAUTHORIZED = AutoEnum.auto()
    SERVER_CONNECTED = AutoEnum.auto()
    SERVER_ERROR = AutoEnum.auto()
    UNCONFIGURED = AutoEnum.auto()
    EPHEMERAL = AutoEnum.auto()
    INVALID_API = AutoEnum.auto()


async def check_server_connection() -> ConnectionStatus:
    httpx_settings = dict(timeout=3)
    try:
        # First determine the server type based on the URL
        server_type = determine_server_type()

        # Only try to connect to Cloud if the URL looks like a Cloud URL
        if server_type == ServerType.CLOUD:
            from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client

            try:
                cloud_client = get_cloud_client(
                    httpx_settings=httpx_settings, infer_cloud_url=True
                )
                async with cloud_client:
                    await cloud_client.api_healthcheck()
                return ConnectionStatus.CLOUD_CONNECTED
            except CloudUnauthorizedError:
                # if the Cloud API exists and fails to authenticate, notify the user
                return ConnectionStatus.CLOUD_UNAUTHORIZED
            except (httpx.HTTPStatusError, Exception):
                return ConnectionStatus.CLOUD_ERROR

        # For non-Cloud URLs, try to connect as a hosted Prefect instance
        if server_type == ServerType.EPHEMERAL:
            return ConnectionStatus.EPHEMERAL
        elif server_type == ServerType.UNCONFIGURED:
            return ConnectionStatus.UNCONFIGURED

        # Try to connect to the server
        try:
            client = get_client(httpx_settings=httpx_settings)
            async with client:
                connect_error = await client.api_healthcheck()
            if connect_error is not None:
                return ConnectionStatus.SERVER_ERROR
            else:
                return ConnectionStatus.SERVER_CONNECTED
        except Exception:
            return ConnectionStatus.SERVER_ERROR
    except TypeError:
        # if no Prefect API URL has been set, httpx will throw a TypeError
        try:
            # try to connect with the client anyway, it will likely use an
            # ephemeral Prefect instance
            server_type = determine_server_type()
            if server_type == ServerType.EPHEMERAL:
                return ConnectionStatus.EPHEMERAL
            elif server_type == ServerType.UNCONFIGURED:
                return ConnectionStatus.UNCONFIGURED
            client = get_client(httpx_settings=httpx_settings)
            if client.server_type == ServerType.EPHEMERAL:
                return ConnectionStatus.EPHEMERAL
            async with client:
                connect_error = await client.api_healthcheck()
            if connect_error is not None:
                return ConnectionStatus.SERVER_ERROR
            else:
                return ConnectionStatus.SERVER_CONNECTED
        except Exception:
            return ConnectionStatus.SERVER_ERROR
    except (httpx.ConnectError, httpx.UnsupportedProtocol):
        return ConnectionStatus.INVALID_API
