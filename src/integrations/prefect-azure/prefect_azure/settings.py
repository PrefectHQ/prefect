from __future__ import annotations

from typing import Optional

from pydantic import Field

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class PostgresManagedIdentitySettings(PrefectBaseSettings):
    """Settings for controlling Azure managed-identity authentication to Postgres."""

    model_config = build_settings_config(
        ("integrations", "azure", "postgres", "managed_identity")
    )

    enabled: bool = Field(
        default=False,
        description=(
            "Controls whether to use Azure managed identity (Microsoft Entra ID) "
            "authentication for Azure Database for PostgreSQL connections."
        ),
    )

    client_id: Optional[str] = Field(
        default=None,
        description=(
            "Client ID of the user-assigned managed identity to authenticate with. "
            "If not provided, the identity resolved by DefaultAzureCredential is used "
            "(e.g. a system-assigned identity or the local developer credential)."
        ),
    )


class PostgresSettings(PrefectBaseSettings):
    """Settings for Azure Database for PostgreSQL integration."""

    model_config = build_settings_config(("integrations", "azure", "postgres"))

    managed_identity: PostgresManagedIdentitySettings = Field(
        description="Settings for controlling Azure managed-identity authentication to Postgres.",
        default_factory=PostgresManagedIdentitySettings,
    )


class AzureSettings(PrefectBaseSettings):
    model_config = build_settings_config(("integrations", "azure"))

    postgres: PostgresSettings = Field(
        description="Settings for controlling Azure Database for PostgreSQL behavior.",
        default_factory=PostgresSettings,
    )
