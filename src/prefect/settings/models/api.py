import os
from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import SettingsConfigDict

from prefect.settings.base import PrefectBaseSettings


class APISettings(PrefectBaseSettings):
    """
    Settings for interacting with the Prefect API
    """

    model_config = SettingsConfigDict(
        env_prefix="PREFECT_API_", env_file=".env", extra="ignore"
    )
    url: Optional[str] = Field(
        default=None,
        description="The URL of the Prefect API. If not set, the client will attempt to infer it.",
    )
    key: Optional[SecretStr] = Field(
        default=None,
        description="The API key used for authentication with the Prefect API. Should be kept secret.",
    )
    tls_insecure_skip_verify: bool = Field(
        default=False,
        description="If `True`, disables SSL checking to allow insecure requests. This is recommended only during development, e.g. when using self-signed certificates.",
    )
    ssl_cert_file: Optional[str] = Field(
        default=os.environ.get("SSL_CERT_FILE"),
        description="This configuration settings option specifies the path to an SSL certificate file.",
    )
    enable_http2: bool = Field(
        default=False,
        description="If true, enable support for HTTP/2 for communicating with an API. If the API does not support HTTP/2, this will have no effect and connections will be made via HTTP/1.1.",
    )
    request_timeout: float = Field(
        default=60.0,
        description="The default timeout for requests to the API",
    )
