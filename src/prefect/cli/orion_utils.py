from contextlib import nullcontext

from prefect.cli.cloud import CloudUnauthorizedError, get_cloud_client
from prefect.client import get_client


async def check_orion_connection(profile_name=None):
    profile_manager = (
        use_profile(profile_name, include_current_context=False)
        if profile_name
        else nullcontext
    )

    with profile_manager:
        httpx_settings = dict(timeout=3)
        try:
            # attempt to infer Cloud 2.0 API from the connection URL
            cloud_client = get_cloud_client(
                httpx_settings=httpx_settings, infer_cloud_url=True
            )
            await cloud_client.api_healthcheck()
            return "cloud"
        except CloudUnauthorizedError:
            # if the Cloud 2.0 API exists and fails to authenticate, notify the user
            return "authentication error"
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                # if the route does not exist, attmpt to connect as a hosted Orion instance
                try:
                    # inform the user if Prefect Orion endpoints exist, but there are
                    # connection issues
                    client = get_client(httpx_settings=httpx_settings)
                    connect_error = await client.api_healthcheck()
                    if connect_error is not None:
                        "Orion connection error"
                    elif await client.using_ephemeral_app():
                        # if the client is using an ephemeral Orion app, inform the user
                        exit_method, msg = (
                            exit_with_success,
                            f"No Prefect Orion instance specified using profile {profile_name!r}. "
                            f"Flow run metadata will be stored at the locally configured database: {prefect.settings.PREFECT_ORION_DATABASE_CONNECTION_URL.value()}",
                        )
                    else:
                        exit_method, msg = (
                            exit_with_success,
                            f"Connected to Prefect Orion using profile {profile_name!r}",
                        )
                except Exception as exc:
                    exit_method, msg = (
                        exit_with_error,
                        f"Error connecting to Prefect Orion using profile {profile_name!r}",
                    )
            else:
                exit_method, msg = (
                    exit_with_error,
                    f"Error connecting to Prefect Cloud: {exc!r}",
                )
        except TypeError:
            # if no Prefect Orion API URL has been set, httpx will throw a TypeError
            try:
                # try to connect with the client anyway, it will likely use an
                # ephemeral Orion instance
                client = get_client(httpx_settings=httpx_settings)
                connect_error = await client.api_healthcheck()
                if connect_error is not None:
                    exit_method, msg = (
                        exit_with_error,
                        f"Error connecting to Prefect Orion using profile {profile_name!r}",
                    )
                elif await client.using_ephemeral_app():
                    exit_method, msg = (
                        exit_with_success,
                        f"No Prefect Orion instance specified using profile {profile_name!r}. "
                        f"Flow run metadata will be stored at the locally configured database: {prefect.settings.PREFECT_ORION_DATABASE_CONNECTION_URL.value()}",
                    )
                else:
                    exit_method, msg = (
                        exit_with_success,
                        f"Connected to Prefect Orion using profile {profile_name!r}",
                    )
            except Exception as exc:
                exit_method, msg = (
                    exit_with_error,
                    f"Error connecting to Prefect Orion using profile {profile_name!r}",
                )
        except (httpx.ConnectError, httpx.UnsupportedProtocol) as exc:
            exit_method, msg = exit_with_error, "Invalid Prefect API URL"

    return exit_method, msg
