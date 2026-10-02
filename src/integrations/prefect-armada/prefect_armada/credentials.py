"""Module for defining Armada credential handling and client generation."""

from __future__ import annotations

import base64
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import grpc
from armada_client.asyncio_client import ArmadaAsyncIOClient
from armada_client.client import ArmadaClient

# `BinocularsClient` is the only client Armada ships for log retrieval. The
# public `armada_client.log_client.JobLogClient` wrapper builds its own channel
# and cannot carry call credentials, so we build the channel ourselves.
from armada_client.internal.binoculars_client import BinocularsClient
from pydantic import Field, SecretStr
from typing_extensions import Self

from prefect.blocks.core import Block
from prefect_armada.settings import ArmadaSettings
from prefect_armada.utilities import _grpc_keepalive_options

ArmadaClientType = ArmadaClient | ArmadaAsyncIOClient


class _BearerAuth(grpc.AuthMetadataPlugin):
    """gRPC auth plugin that sends a bearer token in the `authorization` header."""

    def __init__(self, token: str) -> None:
        self._token = token
        super().__init__()

    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback,
    ) -> None:
        """Sends the bearer token to gRPC as request metadata."""
        callback((("authorization", self._token),), None)


class _BasicAuth(grpc.AuthMetadataPlugin):
    """gRPC auth plugin that sends basic auth credentials per RFC 2617."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        super().__init__()

    def __call__(
        self,
        context: grpc.AuthMetadataContext,
        callback: grpc.AuthMetadataPluginCallback,
    ) -> None:
        """Sends the encoded credentials to gRPC as request metadata."""
        encoded = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode("ascii")
        callback((("authorization", f"basic {encoded}"),), None)


class ArmadaClusterConfig(Block):
    """
    Stores configuration for interaction with an Armada cluster.

    See `from_env` for creation from the current environment.

    Attributes:
        host: The hostname of the Armada server's gRPC endpoint
        port: The port of the Armada server's gRPC endpoint
        disable_ssl: Whether to connect without TLS
        root_certificates: PEM root certificates verifying Armada's TLS certificate
        root_certificates_path: Path to a PEM file of root certificates
        binoculars_host: The hostname of Armada's Binoculars endpoint
        binoculars_port: The port of Armada's Binoculars endpoint

    Example:
        Load a saved Armada cluster config:
        ```python
        from prefect_armada.credentials import ArmadaClusterConfig

        cluster_config_block = ArmadaClusterConfig.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Armada Cluster Config"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-armada"

    host: str = Field(
        default="localhost",
        description="The hostname of the Armada server's gRPC endpoint.",
    )
    port: int = Field(
        default=50051,
        description="The port of the Armada server's gRPC endpoint.",
    )
    disable_ssl: bool = Field(
        default=False,
        description="Whether to connect to Armada without TLS.",
    )
    root_certificates: SecretStr | None = Field(
        default=None,
        description=(
            "PEM-encoded root certificates used to verify the Armada server's "
            "TLS certificate. Takes precedence over `root_certificates_path`. "
            "If neither is provided, gRPC's default roots are used."
        ),
    )
    root_certificates_path: Path | None = Field(
        default=None,
        description=(
            "Path to a PEM file holding the root certificates used to verify the "
            "Armada server's TLS certificate. The file is read when a channel is "
            "opened, so it must be readable by the worker. Ignored when "
            "`root_certificates` is set."
        ),
        examples=["/etc/prefect/armada/ca.crt"],
    )
    binoculars_host: str | None = Field(
        default=None,
        description=(
            "The hostname of Armada's Binoculars gRPC endpoint, which serves job "
            "logs. Defaults to the Armada server host."
        ),
    )
    binoculars_port: int = Field(
        default=50053,
        description=(
            "The port of Armada's Binoculars gRPC endpoint, which serves job logs."
        ),
    )
    channel_options: dict[str, Any] = Field(
        default_factory=dict,
        title="Channel Options",
        description="Additional gRPC channel options to use when connecting to Armada.",
        examples=[{"grpc.max_receive_message_length": 16777216}],
    )
    add_grpc_keepalive: bool = Field(
        default=True,
        description=(
            "Whether to enable gRPC keepalive pings, which keep long-lived Armada "
            "event streams from being dropped by idle connection timeouts."
        ),
    )
    event_timeout_seconds: int = Field(
        default=900,
        description=(
            "How long an Armada event stream may go without a message before it is "
            "reconnected."
        ),
    )

    @classmethod
    def from_env(cls: type[Self]) -> Self:
        """
        Create a cluster config from the current environment.

        Values are read from `PREFECT_INTEGRATIONS_ARMADA_CONNECTION_*` settings,
        falling back to the `ARMADA_SERVER` and `ARMADA_PORT` environment
        variables used by Armada's own tooling.
        """
        connection = ArmadaSettings().connection
        return cls(
            host=connection.host,
            port=connection.port,
            disable_ssl=connection.disable_ssl,
            root_certificates=connection.root_certificates,
            root_certificates_path=connection.root_certificates_path,
            binoculars_host=connection.binoculars_host,
            binoculars_port=connection.binoculars_port,
        )

    @property
    def target(self) -> str:
        """The gRPC target for the Armada server, in `host:port` form."""
        return f"{self.host}:{self.port}"

    @property
    def binoculars_target(self) -> str:
        """The gRPC target for Armada's Binoculars service, in `host:port` form."""
        return f"{self.binoculars_host or self.host}:{self.binoculars_port}"

    def get_channel_options(self) -> list[tuple[str, Any]]:
        """
        Returns the gRPC channel options to use when connecting to Armada.
        """
        options: list[tuple[str, Any]] = []
        if self.add_grpc_keepalive:
            options.extend(_grpc_keepalive_options())
        options.extend(self.channel_options.items())
        return options

    def _resolve_root_certificates(self) -> bytes | None:
        """
        Returns the PEM root certificates to verify Armada's TLS certificate.

        Inline `root_certificates` take precedence over `root_certificates_path`.
        Returns `None` when neither is set, in which case gRPC's default roots
        are used.
        """
        if self.root_certificates:
            return self.root_certificates.get_secret_value().encode()
        if self.root_certificates_path is None:
            return None

        path = Path(self.root_certificates_path).expanduser()
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"Could not read Armada root certificates from {path}: {exc}"
            ) from exc

    def get_channel_credentials(
        self, call_credentials: grpc.CallCredentials | None = None
    ) -> grpc.ChannelCredentials | None:
        """
        Returns the gRPC channel credentials for this cluster config.

        Args:
            call_credentials: Per-call credentials to compose with the channel
                credentials, for example an authorization header.

        Returns:
            The channel credentials to use, or `None` when an insecure channel
            should be used instead.
        """
        if self.disable_ssl:
            if call_credentials is None:
                # No credentials to carry; an insecure channel is sufficient.
                return None
            # gRPC refuses to send call credentials over an insecure channel, so
            # local channel credentials are used to carry them, matching the
            # pattern in Armada's own client examples.
            channel_credentials = grpc.local_channel_credentials()
        else:
            # `ssl_channel_credentials` falls back to gRPC's default roots when
            # `root_certificates` is None.
            channel_credentials = grpc.ssl_channel_credentials(
                root_certificates=self._resolve_root_certificates()
            )

        if call_credentials is None:
            return channel_credentials

        return grpc.composite_channel_credentials(channel_credentials, call_credentials)


class ArmadaCredentials(Block):
    """Credentials block for generating configured Armada API clients.

    Attributes:
        cluster_config: An `ArmadaClusterConfig` block holding the connection
            details for an Armada cluster. If not provided, connection details
            are read from the current environment.
        token: A bearer token to authenticate with Armada.
        username: The username to authenticate with Armada using basic auth.
        password: The password to authenticate with Armada using basic auth.

    Example:
        Load stored Armada credentials:
        ```python
        from prefect_armada.credentials import ArmadaCredentials

        armada_credentials = ArmadaCredentials.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Armada Credentials"
    _documentation_url = "https://docs.prefect.io/integrations/prefect-armada"

    cluster_config: ArmadaClusterConfig | None = None

    token: SecretStr | None = Field(
        default=None,
        description=(
            "A bearer token to authenticate with Armada. The token is sent verbatim "
            "in the `authorization` header, so it should include the `Bearer` prefix "
            "if the Armada server expects one."
        ),
    )
    username: str | None = Field(
        default=None,
        description="The username to authenticate with Armada using basic auth.",
    )
    password: SecretStr | None = Field(
        default=None,
        description="The password to authenticate with Armada using basic auth.",
    )

    def get_cluster_config(self) -> ArmadaClusterConfig:
        """
        Returns the cluster config for this credentials block.

        Falls back to a config built from the current environment when this
        block does not have one.
        """
        if self.cluster_config:
            return self.cluster_config
        return ArmadaClusterConfig.from_env()

    def get_call_credentials(self) -> grpc.CallCredentials | None:
        """
        Returns the gRPC call credentials for this credentials block.

        Returns:
            Call credentials carrying an authorization header, or `None` if no
            authentication is configured.
        """
        settings = ArmadaSettings().connection
        token = self.token or settings.token
        username = self.username or settings.username
        password = self.password or settings.password

        if token:
            return grpc.metadata_call_credentials(_BearerAuth(token.get_secret_value()))
        if username and password:
            return grpc.metadata_call_credentials(
                _BasicAuth(username, password.get_secret_value())
            )
        return None

    def _new_channel(self, target: str, asynchronous: bool) -> grpc.Channel:
        """Opens a gRPC channel to the given Armada target."""
        cluster_config = self.get_cluster_config()
        options = cluster_config.get_channel_options()
        credentials = cluster_config.get_channel_credentials(
            self.get_call_credentials()
        )
        grpc_module = grpc.aio if asynchronous else grpc
        if credentials is None:
            return grpc_module.insecure_channel(target, options=options)
        return grpc_module.secure_channel(target, credentials, options=options)

    @asynccontextmanager
    async def get_client(self) -> AsyncGenerator[ArmadaAsyncIOClient, None]:
        """Convenience method for retrieving an asynchronous Armada API client.

        Yields:
            An authenticated `ArmadaAsyncIOClient`.

        Example:
            ```python
            from prefect_armada.credentials import ArmadaCredentials

            async with ArmadaCredentials().get_client() as client:
                for queue in await client.get_queues():
                    print(queue.name)
            ```
        """
        cluster_config = self.get_cluster_config()
        channel = self._new_channel(cluster_config.target, asynchronous=True)
        try:
            yield ArmadaAsyncIOClient(
                channel=channel,
                event_timeout=timedelta(seconds=cluster_config.event_timeout_seconds),
            )
        finally:
            await channel.close()

    @contextmanager
    def get_sync_client(self) -> Generator[ArmadaClient, None, None]:
        """Convenience method for retrieving a synchronous Armada API client.

        Yields:
            An authenticated `ArmadaClient`.

        Example:
            ```python
            from prefect_armada.credentials import ArmadaCredentials

            with ArmadaCredentials().get_sync_client() as client:
                for queue in client.get_queues():
                    print(queue.name)
            ```
        """
        cluster_config = self.get_cluster_config()
        channel = self._new_channel(cluster_config.target, asynchronous=False)
        try:
            yield ArmadaClient(
                channel=channel,
                event_timeout=timedelta(seconds=cluster_config.event_timeout_seconds),
            )
        finally:
            channel.close()

    @contextmanager
    def get_binoculars_client(self) -> Generator[BinocularsClient, None, None]:
        """Convenience method for retrieving a client for Armada's log service.

        Armada serves job logs from its Binoculars service, which only has a
        synchronous client. Callers in async code should run its methods in a
        worker thread.

        Yields:
            An authenticated `BinocularsClient`.
        """
        cluster_config = self.get_cluster_config()
        channel = self._new_channel(
            cluster_config.binoculars_target, asynchronous=False
        )
        try:
            yield BinocularsClient(channel=channel)
        finally:
            channel.close()
