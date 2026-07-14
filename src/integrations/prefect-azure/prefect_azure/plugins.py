from __future__ import annotations

import ssl
from typing import Any, Mapping

from azure.identity.aio import DefaultAzureCredential

# `register_hook` graduated to `prefect.plugins` once the system reached GA.
# Fall back to the experimental path so this entry point keeps loading on
# older Prefect releases that pre-date the GA promotion.
try:
    from prefect.plugins import register_hook
except ImportError:  # pragma: no cover - exercised on older Prefect installs
    from prefect._experimental.plugins import register_hook

from prefect_azure.settings import AzureSettings

# Microsoft Entra scope for Azure Database for PostgreSQL authentication.
OSSRDBMS_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"


@register_hook
def set_database_connection_params(
    connection_url: str, settings: Any
) -> Mapping[str, Any]:
    """Provide Microsoft Entra ID (managed identity) auth params for Postgres.

    Prefect calls this hook when building its server database engine and merges
    the returned mapping into asyncpg's `connect_args`. When managed-identity auth
    is enabled (`AzureSettings().postgres.managed_identity.enabled`), this returns
    a `password` callable that mints a short-lived Entra token via
    `DefaultAzureCredential` and an SSL context. asyncpg invokes the callable on
    every new connection, so tokens refresh automatically and no database password
    is required. Returns an empty mapping when the feature is disabled.

    Args:
        connection_url: The database connection URL (unused; the username and host
            come from the URL Prefect already built).
        settings: The current Prefect settings (unused; integration settings are
            read from `AzureSettings`).

    Returns:
        A mapping of asyncpg connection parameters to merge into `connect_args`,
        or an empty mapping when managed-identity auth is disabled.
    """
    mi_settings = AzureSettings().postgres.managed_identity

    if not mi_settings.enabled:
        return {}

    connect_args: dict[str, Any] = {}

    # Instantiate the credential once per engine so its internal token cache is
    # reused across connections; a per-connection credential would have an empty
    # cache and could throttle the token endpoint.
    credential = DefaultAzureCredential(
        managed_identity_client_id=mi_settings.client_id
    )

    async def get_token() -> str:
        # asyncpg awaits this on every new connection; azure-identity returns a
        # cached token until it is near expiry, then transparently refreshes it.
        token = await credential.get_token(OSSRDBMS_SCOPE)
        return token.token

    # Microsoft Entra authentication requires SSL.
    # Use create_default_context() for secure defaults (cert verification enabled).
    connect_args["ssl"] = ssl.create_default_context()
    connect_args["password"] = get_token

    return connect_args
