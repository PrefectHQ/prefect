import httpx
from fastapi import status

from prefect.cli.cloud import CloudUnauthorizedError, get_cloud_client
from prefect.client import get_client
from prefect.settings import PREFECT_API_URL
from prefect.utilities.collections import AutoEnum


class ConnectionStatus(AutoEnum):
    CLOUD_CONNECTED = AutoEnum.auto()
    CLOUD_ERROR = AutoEnum.auto()
    CLOUD_UNAUTHORIZED = AutoEnum.auto()
    ORION_CONNECTED = AutoEnum.auto()
    ORION_ERROR = AutoEnum.auto()
    EPHEMERAL = AutoEnum.auto()
    INVALID_API = AutoEnum.auto()


async def check_orion_connection():
    httpx_settings = dict(timeout=3)
    try:
        # attempt to infer Cloud 2.0 API from the connection URL
        cloud_client = get_cloud_client(
            httpx_settings=httpx_settings, infer_cloud_url=True
        )
        await cloud_client.api_healthcheck()
        return ConnectionStatus.CLOUD_CONNECTED
    except CloudUnauthorizedError:
        # if the Cloud 2.0 API exists and fails to authenticate, notify the user
        return ConnectionStatus.CLOUD_UNAUTHORIZED
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == status.HTTP_404_NOT_FOUND:
            # if the route does not exist, attmpt to connect as a hosted Orion instance
            try:
                # inform the user if Prefect Orion endpoints exist, but there are
                # connection issues
                client = get_client(httpx_settings=httpx_settings)
                connect_error = await client.api_healthcheck()
                if connect_error is not None:
                    return ConnectionStatus.ORION_ERROR
                elif await client.using_ephemeral_app():
                    # if the client is using an ephemeral Orion app, inform the user
                    return ConnectionStatus.EPHEMERAL
                else:
                    return ConnectionStatus.ORION_CONNECTED
            except Exception as exc:
                return ConnectionStatus.ORION_ERROR
        else:
            return ConnectionStatus.CLOUD_ERROR
    except TypeError:
        # if no Prefect Orion API URL has been set, httpx will throw a TypeError
        try:
            # try to connect with the client anyway, it will likely use an
            # ephemeral Orion instance
            client = get_client(httpx_settings=httpx_settings)
            connect_error = await client.api_healthcheck()
            if connect_error is not None:
                return ConnectionStatus.ORION_ERROR
            elif await client.using_ephemeral_app():
                return ConnectionStatus.EPHEMERAL
            else:
                return ConnectionStatus.ORION_CONNECTED
        except Exception as exc:
            return ConnectionStatus.ORION_ERROR
    except (httpx.ConnectError, httpx.UnsupportedProtocol) as exc:
        return ConnectionStatus.INVALID_API

    return exit_method, msg


def ui_base_url(connection_status):
    if connection_status == ConnectionStatus.CLOUD_CONNECTED:
        ui_url = PREFECT_API_URL.value()
        ui_url = ui_url.replace("https://api.", "https://app.")
        ui_url = ui_url.replace("/api/accounts/", "/account/")
        ui_url = ui_url.replace("/workspaces/", "/workspace/")
        return ui_url
    if connection_status == ConnectionStatus.ORION_CONNECTED:
        ui_url = PREFECT_API_URL.value()
        ui_url = ui_url.strip("/api")
        return ui_url
    else:
        return None
