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
