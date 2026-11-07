from datetime import timedelta
from typing import ClassVar, Optional

from pydantic import AliasChoices, AliasPath, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings, build_settings_config


class ServerAPISettings(PrefectBaseSettings):
    """
    Settings for controlling API server behavior
    """

    model_config: ClassVar[SettingsConfigDict] = build_settings_config(
        ("server", "api")
    )

    auth_string: Optional[SecretStr] = Field(
        default=None,
        description="A string to use for basic authentication with the API in the form 'user:password'.",
    )

    host: str = Field(
        default="127.0.0.1",
        description="The API's host address (defaults to `127.0.0.1`).",
    )

    port: int = Field(
        default=4200,
        description="The API's port address (defaults to `4200`).",
    )

    base_path: Optional[str] = Field(
        default=None,
        description="The base URL path to serve the API under.",
        examples=["/v2/api"],
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

    # -------------------------------------------------------------------------
    # Optional fastapi-guard security middleware (prefect/server/api/guard.py)
    # -------------------------------------------------------------------------
    # Opt-in request screening for deployments exposing the server directly:
    # IP block/allow lists, rate limiting with auto-ban, user-agent blocking,
    # penetration detection. Default off; the disabled path imports nothing.
    # Requires the fastapi-guard dependency.
    guard_enabled: bool = Field(
        default=False,
        description="""
        Enables the optional fastapi-guard security middleware for the server
        API. When enabled, the server applies IP block/allow lists, rate
        limiting with auto-ban, user-agent blocking, and penetration-attempt
        detection to incoming requests. Requires the fastapi-guard dependency;
        enabling it without the dependency installed raises an error at
        startup. Defaults to `False`.
        """,
        validation_alias=AliasChoices(
            AliasPath("guard_enabled"),
            "prefect_server_api_guard_enabled",
        ),
    )
    guard_rate_limit: int = Field(
        default=100,
        description="Maximum requests per IP per rate limiting window when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_rate_limit"),
            "prefect_server_api_guard_rate_limit",
        ),
    )
    guard_rate_limit_window: int = Field(
        default=60,
        description="Rate limiting window in seconds when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_rate_limit_window"),
            "prefect_server_api_guard_rate_limit_window",
        ),
    )
    guard_auto_ban_threshold: int = Field(
        default=10,
        description="Number of suspicious events before an IP is banned when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_auto_ban_threshold"),
            "prefect_server_api_guard_auto_ban_threshold",
        ),
    )
    guard_auto_ban_duration: int = Field(
        default=300,
        description="Duration of automatic IP bans in seconds when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_auto_ban_duration"),
            "prefect_server_api_guard_auto_ban_duration",
        ),
    )
    guard_passive_mode: bool = Field(
        default=False,
        description="""
        When `True`, the guard middleware logs violations without blocking
        requests. Useful for observing what would be blocked before
        enforcing.
        """,
        validation_alias=AliasChoices(
            AliasPath("guard_passive_mode"),
            "prefect_server_api_guard_passive_mode",
        ),
    )
    guard_blocked_ips: Optional[str] = Field(
        default=None,
        description="Comma-separated IPs or CIDR ranges to block when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_blocked_ips"),
            "prefect_server_api_guard_blocked_ips",
        ),
    )
    guard_allowed_ips: Optional[str] = Field(
        default=None,
        description="Comma-separated IPs or CIDR ranges to allow through the guard middleware; when set, all other IPs are blocked.",
        validation_alias=AliasChoices(
            AliasPath("guard_allowed_ips"),
            "prefect_server_api_guard_allowed_ips",
        ),
    )
    guard_blocked_user_agents: Optional[str] = Field(
        default=None,
        description="Comma-separated user-agent substrings to block when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_blocked_user_agents"),
            "prefect_server_api_guard_blocked_user_agents",
        ),
    )
    guard_trusted_proxies: Optional[str] = Field(
        default=None,
        description="""
        Comma-separated proxy IPs or CIDR ranges trusted for
        X-Forwarded-For resolution when the guard middleware is enabled.
        Leave unset to keep client-supplied forwarding headers untrusted.
        """,
        validation_alias=AliasChoices(
            AliasPath("guard_trusted_proxies"),
            "prefect_server_api_guard_trusted_proxies",
        ),
    )
    guard_trusted_proxy_depth: int = Field(
        default=1,
        description="Number of trusted proxies to walk in X-Forwarded-For when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_trusted_proxy_depth"),
            "prefect_server_api_guard_trusted_proxy_depth",
        ),
    )
    guard_excluded_paths: Optional[str] = Field(
        default=None,
        description="""
        Comma-separated path prefixes excluded from guard detection checks.
        Defaults to health, docs and OpenAPI paths. Global IP lists still
        apply on excluded paths.
        """,
        validation_alias=AliasChoices(
            AliasPath("guard_excluded_paths"),
            "prefect_server_api_guard_excluded_paths",
        ),
    )
    guard_blocked_countries: Optional[str] = Field(
        default=None,
        description="Comma-separated ISO country codes to block when the guard middleware is enabled. Requires IPINFO_TOKEN geo lookups.",
        validation_alias=AliasChoices(
            AliasPath("guard_blocked_countries"),
            "prefect_server_api_guard_blocked_countries",
        ),
    )
    guard_allowed_countries: Optional[str] = Field(
        default=None,
        description="Comma-separated ISO country codes to allow when the guard middleware is enabled. Requires IPINFO_TOKEN geo lookups.",
        validation_alias=AliasChoices(
            AliasPath("guard_allowed_countries"),
            "prefect_server_api_guard_allowed_countries",
        ),
    )
    guard_block_cloud_providers: Optional[str] = Field(
        default=None,
        description="Comma-separated cloud provider names (e.g. AWS, GCP, Azure) to block when the guard middleware is enabled. Requires IPINFO_TOKEN.",
        validation_alias=AliasChoices(
            AliasPath("guard_block_cloud_providers"),
            "prefect_server_api_guard_block_cloud_providers",
        ),
    )
    guard_redis_url: Optional[str] = Field(
        default=None,
        description="""
        Redis URL for guard state shared across workers and replicas when
        the guard middleware is enabled. Unset keeps counters and bans
        in-memory per process.
        """,
        validation_alias=AliasChoices(
            AliasPath("guard_redis_url"),
            "prefect_server_api_guard_redis_url",
        ),
    )
    guard_ipinfo_token: Optional[str] = Field(
        default=None,
        description="IPInfo token for geo and cloud-provider lookups when the guard middleware is enabled.",
        validation_alias=AliasChoices(
            AliasPath("guard_ipinfo_token"),
            "prefect_server_api_guard_ipinfo_token",
        ),
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

    websocket_ping_interval: float = Field(
        default=20.0,
        description="WebSocket ping interval in seconds. Only applies when starting the server with `prefect server start`.",
    )

    websocket_ping_timeout: float = Field(
        default=20.0,
        description="WebSocket ping timeout in seconds. Only applies when starting the server with `prefect server start`.",
    )

    max_parameter_size: int = Field(
        default=524_288,
        description="The maximum size of parameters (in bytes, JSON-serialized) that can be stored on a flow run or deployment. Set to 0 to disable the limit.",
        ge=0,
    )
