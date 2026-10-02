from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Annotated

from pydantic import AliasChoices, AliasPath, BeforeValidator, Field, SecretStr

from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.types import validate_set_T_from_delim_string

JobSets = Annotated[
    set[str] | str | None,
    BeforeValidator(partial(validate_set_T_from_delim_string, type_=str)),
]


class ArmadaConnectionSettings(PrefectBaseSettings):
    """Settings for connecting to an Armada server."""

    model_config = build_settings_config(("integrations", "armada", "connection"))

    host: str = Field(
        default="localhost",
        description="The hostname of the Armada server's gRPC endpoint.",
        validation_alias=AliasChoices(
            AliasPath("host"),
            "prefect_integrations_armada_connection_host",
            # Matches the environment variable used by Armada's own tooling
            # and examples.
            "armada_server",
        ),
    )

    port: int = Field(
        default=50051,
        description="The port of the Armada server's gRPC endpoint.",
        validation_alias=AliasChoices(
            AliasPath("port"),
            "prefect_integrations_armada_connection_port",
            "armada_port",
        ),
    )

    disable_ssl: bool = Field(
        default=False,
        description="Whether to connect to Armada without TLS.",
        validation_alias=AliasChoices(
            AliasPath("disable_ssl"),
            "prefect_integrations_armada_connection_disable_ssl",
            # `DISABLE_SSL` itself cannot be used here: Prefect's settings
            # sources filter out unprefixed environment variables that share a
            # name with a field.
            "armada_disable_ssl",
        ),
    )

    root_certificates: SecretStr | None = Field(
        default=None,
        description="PEM-encoded root certificates used to verify the Armada "
        "server's TLS certificate. Takes precedence over "
        "`root_certificates_path`. If neither is set, gRPC's default roots are "
        "used.",
        validation_alias=AliasChoices(
            AliasPath("root_certificates"),
            "prefect_integrations_armada_connection_root_certificates",
            "armada_root_certificates",
        ),
    )

    root_certificates_path: Path | None = Field(
        default=None,
        description="Path to a PEM file holding the root certificates used to "
        "verify the Armada server's TLS certificate. Ignored when "
        "`root_certificates` is set.",
        validation_alias=AliasChoices(
            AliasPath("root_certificates_path"),
            "prefect_integrations_armada_connection_root_certificates_path",
            "armada_root_certificates_path",
        ),
    )

    binoculars_host: str | None = Field(
        default=None,
        description="The hostname of Armada's Binoculars gRPC endpoint, which "
        "serves job logs. Defaults to the Armada server host.",
    )

    binoculars_port: int = Field(
        default=50053,
        description="The port of Armada's Binoculars gRPC endpoint, which serves job logs.",
    )

    token: SecretStr | None = Field(
        default=None,
        description="A bearer token to authenticate with Armada. The token is sent "
        "verbatim in the `authorization` header, so it should not include the "
        "`Bearer` prefix.",
    )

    username: str | None = Field(
        default=None,
        description="The username to authenticate with Armada using basic auth.",
    )

    password: SecretStr | None = Field(
        default=None,
        description="The password to authenticate with Armada using basic auth.",
    )


class ArmadaWorkerSubmitJobRetrySettings(PrefectBaseSettings):
    """Settings for retrying Armada job submissions."""

    model_config = build_settings_config(
        ("integrations", "armada", "worker", "submit_job_retry")
    )

    max_retries: int = Field(
        default=3,
        ge=1,
        description="The maximum number of attempts to submit an Armada job before giving up.",
    )

    delay_seconds: int = Field(
        default=1,
        ge=0,
        description="The fixed delay in seconds between retries when submitting an Armada job.",
    )

    jitter_min_seconds: int = Field(
        default=0,
        ge=0,
        description="The minimum jitter in seconds to add to the delay between retries when submitting an Armada job.",
    )

    jitter_max_seconds: int = Field(
        default=3,
        ge=0,
        description="The maximum jitter in seconds to add to the delay between retries when submitting an Armada job.",
    )


class ArmadaWorkerSettings(PrefectBaseSettings):
    """Settings for the Armada worker."""

    model_config = build_settings_config(("integrations", "armada", "worker"))

    default_queue: str = Field(
        default="prefect",
        description="The Armada queue jobs are submitted to when a work pool does "
        "not specify one.",
    )

    add_grpc_keepalive: bool = Field(
        default=True,
        description="If `True`, the worker will enable gRPC keepalive pings on "
        "channels it opens to Armada.",
    )

    submit_job_retry: ArmadaWorkerSubmitJobRetrySettings = Field(
        description="Settings for controlling retry behavior when submitting Armada jobs.",
        default_factory=ArmadaWorkerSubmitJobRetrySettings,
    )


class ArmadaObserverSettings(PrefectBaseSettings):
    """Settings for the Armada observer."""

    model_config = build_settings_config(("integrations", "armada", "observer"))

    enabled: bool = Field(
        default=True,
        description="Whether the Armada observer is enabled to watch events for "
        "Prefect-submitted Armada jobs.",
    )

    replicate_job_events: bool = Field(
        default=True,
        description="Whether the Armada observer should replicate events for "
        "Prefect-submitted Armada jobs, which can be used for Prefect Automations.",
    )

    job_sets: JobSets = Field(
        default_factory=set,
        description="Armada job sets to watch in addition to the job sets submitted "
        "by this worker, in `<queue>/<job_set_id>` format. Use this to observe job "
        "sets submitted by another process.",
    )

    forward_crashed_run_logs: bool = Field(
        default=True,
        description="Whether to fetch and forward job logs for flow runs that "
        "crashed before establishing connectivity to the Prefect server (for "
        "example a bad entrypoint or missing dependencies).",
    )

    forward_crashed_run_logs_tail_lines: int = Field(
        default=500,
        ge=1,
        description="Number of tail lines to fetch from crashed Armada jobs when "
        "forwarding logs.",
    )

    crashed_run_grace_seconds: int = Field(
        default=30,
        ge=0,
        description="How long to wait for a pending flow run to report its own state "
        "before marking it as crashed after its Armada job has failed.",
    )


class ArmadaSettings(PrefectBaseSettings):
    """Settings for `prefect-armada`."""

    model_config = build_settings_config(("integrations", "armada"))

    cluster_uid: str | None = Field(
        default=None,
        description="A unique identifier for the Armada cluster being used.",
    )

    connection: ArmadaConnectionSettings = Field(
        description="Settings for connecting to Armada when no credentials block is configured.",
        default_factory=ArmadaConnectionSettings,
    )

    worker: ArmadaWorkerSettings = Field(
        description="Settings for controlling Armada worker behavior.",
        default_factory=ArmadaWorkerSettings,
    )

    observer: ArmadaObserverSettings = Field(
        description="Settings for controlling Armada observer behavior.",
        default_factory=ArmadaObserverSettings,
    )
