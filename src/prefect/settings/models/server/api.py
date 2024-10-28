from datetime import timedelta

from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class ServerAPISettings(PrefectBaseSettings):
    """
    Settings for controlling API server behavior
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_SERVER_API_", env_file=".env", extra="ignore"
    )

    host: str = Field(
        default="127.0.0.1",
        description="The API's host address (defaults to `127.0.0.1`).",
    )

    port: int = Field(
        default=4200,
        description="The API's port address (defaults to `4200`).",
    )

    default_limit: int = Field(
        default=200,
        description="The default limit applied to queries that can return multiple objects, such as `POST /flow_runs/filter`.",
        validation_alias=AliasChoices(
            AliasPath("default_limit"),
            "prefect_server_api_default_limit",
            "prefect_api_default_limit",
        ),
    )

    keepalive_timeout: int = Field(
        default=5,
        description="""
        The API's keep alive timeout (defaults to `5`).
        Refer to https://www.uvicorn.org/settings/#timeouts for details.

        When the API is hosted behind a load balancer, you may want to set this to a value
        greater than the load balancer's idle timeout.

        Note this setting only applies when calling `prefect server start`; if hosting the
        API with another tool you will need to configure this there instead.
        """,
    )

    csrf_protection_enabled: bool = Field(
        default=False,
        description="""
        Controls the activation of CSRF protection for the Prefect server API.

        When enabled (`True`), the server enforces CSRF validation checks on incoming
        state-changing requests (POST, PUT, PATCH, DELETE), requiring a valid CSRF
        token to be included in the request headers or body. This adds a layer of
        security by preventing unauthorized or malicious sites from making requests on
        behalf of authenticated users.

        It is recommended to enable this setting in production environments where the
        API is exposed to web clients to safeguard against CSRF attacks.

        Note: Enabling this setting requires corresponding support in the client for
        CSRF token management. See PREFECT_CLIENT_CSRF_SUPPORT_ENABLED for more.
        """,
        validation_alias=AliasChoices(
            AliasPath("csrf_protection_enabled"),
            "prefect_server_api_csrf_protection_enabled",
            "prefect_server_csrf_protection_enabled",
        ),
    )

    csrf_token_expiration: timedelta = Field(
        default=timedelta(hours=1),
        description="""
        Specifies the duration for which a CSRF token remains valid after being issued
        by the server.

        The default expiration time is set to 1 hour, which offers a reasonable
        compromise. Adjust this setting based on your specific security requirements
        and usage patterns.
        """,
        validation_alias=AliasChoices(
            AliasPath("csrf_token_expiration"),
            "prefect_server_api_csrf_token_expiration",
            "prefect_server_csrf_token_expiration",
        ),
    )

    cors_allowed_origins: str = Field(
        default="*",
        description="""
        A comma-separated list of origins that are authorized to make cross-origin requests to the API.

        By default, this is set to `*`, which allows requests from all origins.
        """,
        validation_alias=AliasChoices(
            AliasPath("cors_allowed_origins"),
            "prefect_server_api_cors_allowed_origins",
            "prefect_server_cors_allowed_origins",
        ),
    )

    cors_allowed_methods: str = Field(
        default="*",
        description="""
        A comma-separated list of methods that are authorized to make cross-origin requests to the API.

        By default, this is set to `*`, which allows requests from all methods.
        """,
        validation_alias=AliasChoices(
            AliasPath("cors_allowed_methods"),
            "prefect_server_api_cors_allowed_methods",
            "prefect_server_cors_allowed_methods",
        ),
    )

    cors_allowed_headers: str = Field(
        default="*",
        description="""
        A comma-separated list of headers that are authorized to make cross-origin requests to the API.

        By default, this is set to `*`, which allows requests from all headers.
        """,
        validation_alias=AliasChoices(
            AliasPath("cors_allowed_headers"),
            "prefect_server_api_cors_allowed_headers",
            "prefect_server_cors_allowed_headers",
        ),
    )
