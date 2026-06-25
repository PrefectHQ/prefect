"""
Shared v1 worker-channel protocol contract.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import Annotated, Any, ClassVar, Union
from uuid import UUID

from pydantic import ConfigDict, Field, TypeAdapter, model_validator
from typing_extensions import Literal, TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import WorkPool, WorkPoolStorageConfiguration
from prefect.types import NonNegativeInteger, PositiveInteger
from prefect.types._datetime import DateTime

WORK_POOL_WORKER_CHANNEL_ROUTE: Literal[
    "/work_pools/{work_pool_name}/workers/connect"
] = "/work_pools/{work_pool_name}/workers/connect"
WORK_POOL_WORKER_CHANNEL_VERSION: Literal["work_pool_worker_channel.v1"] = (
    "work_pool_worker_channel.v1"
)
WORKER_CHANNEL_SUBPROTOCOL: Literal["prefect"] = "prefect"

WorkerChannelVersion: TypeAlias = Literal["work_pool_worker_channel.v1"]
WorkerChannelCapability: TypeAlias = Literal[
    "worker_heartbeat.v1",
    "work_pool_snapshot.v1",
    "cleanup_delivery.v1",
]
CleanupKind: TypeAlias = Literal[
    "cancelling_timeout_teardown.v1",
    "pending_claim_teardown.v1",
]
WorkerChannelFrameType: TypeAlias = Literal[
    "worker.hello.v1",
    "worker.ready.v1",
    "worker.heartbeat.v1",
    "work_pool.snapshot.v1",
    "cleanup.message.v1",
    "cleanup.ack.v1",
    "cleanup.release.v1",
    "cleanup.renew.v1",
    "cleanup.operation_result.v1",
]
CleanupOperation: TypeAlias = Literal["ack", "release", "renew"]
CleanupOperationStatus: TypeAlias = Literal[
    "accepted",
    "not_current",
    "not_found",
    "expired",
    "invalid_token",
    "unauthorized",
    "dead_lettered",
    "error",
]
_NonEmptyString: TypeAlias = Annotated[str, Field(min_length=1)]


def _is_non_string_iterable(value: Any) -> bool:
    return isinstance(value, Iterable) and not isinstance(
        value, (str, bytes, bytearray, dict)
    )


WORKER_HEARTBEAT_CAPABILITY: Literal["worker_heartbeat.v1"] = "worker_heartbeat.v1"
WORK_POOL_SNAPSHOT_CAPABILITY: Literal["work_pool_snapshot.v1"] = (
    "work_pool_snapshot.v1"
)
CLEANUP_DELIVERY_CAPABILITY: Literal["cleanup_delivery.v1"] = "cleanup_delivery.v1"

REQUIRED_WORKER_CHANNEL_CAPABILITIES: frozenset[WorkerChannelCapability] = frozenset(
    {
        WORKER_HEARTBEAT_CAPABILITY,
        WORK_POOL_SNAPSHOT_CAPABILITY,
    }
)
OPTIONAL_WORKER_CHANNEL_CAPABILITIES: frozenset[WorkerChannelCapability] = frozenset(
    {CLEANUP_DELIVERY_CAPABILITY}
)
SUPPORTED_WORKER_CHANNEL_CAPABILITIES: frozenset[WorkerChannelCapability] = (
    REQUIRED_WORKER_CHANNEL_CAPABILITIES | OPTIONAL_WORKER_CHANNEL_CAPABILITIES
)

CANCELLING_TIMEOUT_TEARDOWN: Literal["cancelling_timeout_teardown.v1"] = (
    "cancelling_timeout_teardown.v1"
)
PENDING_CLAIM_TEARDOWN: Literal["pending_claim_teardown.v1"] = (
    "pending_claim_teardown.v1"
)
SUPPORTED_CLEANUP_KINDS: tuple[CleanupKind, ...] = (
    CANCELLING_TIMEOUT_TEARDOWN,
    PENDING_CLAIM_TEARDOWN,
)


class WorkerChannelCloseReason(str, Enum):
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_FAILED = "authorization_failed"
    UNSUPPORTED_VERSION = "unsupported_version"
    PROTOCOL_ERROR = "protocol_error"
    HEARTBEAT_PERSISTENCE_FAILED = "heartbeat_persistence_failed"
    TRANSIENT_SERVER_ERROR = "transient_server_error"


class WorkerChannelClosePolicy(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    reason: WorkerChannelCloseReason
    websocket_code: int
    terminal: bool
    retryable: bool


WORKER_CHANNEL_CLOSE_POLICIES: dict[
    WorkerChannelCloseReason, WorkerChannelClosePolicy
] = {
    WorkerChannelCloseReason.AUTHENTICATION_FAILED: WorkerChannelClosePolicy(
        reason=WorkerChannelCloseReason.AUTHENTICATION_FAILED,
        websocket_code=1008,
        terminal=True,
        retryable=False,
    ),
    WorkerChannelCloseReason.AUTHORIZATION_FAILED: WorkerChannelClosePolicy(
        reason=WorkerChannelCloseReason.AUTHORIZATION_FAILED,
        websocket_code=1008,
        terminal=True,
        retryable=False,
    ),
    WorkerChannelCloseReason.UNSUPPORTED_VERSION: WorkerChannelClosePolicy(
        reason=WorkerChannelCloseReason.UNSUPPORTED_VERSION,
        websocket_code=1008,
        terminal=True,
        retryable=False,
    ),
    WorkerChannelCloseReason.PROTOCOL_ERROR: WorkerChannelClosePolicy(
        reason=WorkerChannelCloseReason.PROTOCOL_ERROR,
        websocket_code=1002,
        terminal=True,
        retryable=False,
    ),
    WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED: WorkerChannelClosePolicy(
        reason=WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED,
        websocket_code=1011,
        terminal=False,
        retryable=True,
    ),
    WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR: WorkerChannelClosePolicy(
        reason=WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR,
        websocket_code=1011,
        terminal=False,
        retryable=True,
    ),
}


class WorkerChannelProtocolError(ValueError):
    def __init__(self, close_reason: WorkerChannelCloseReason, message: str):
        super().__init__(message)
        self.close_reason = close_reason


class WorkerChannelContract(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    route: Literal["/work_pools/{work_pool_name}/workers/connect"]
    version: WorkerChannelVersion
    websocket_subprotocol: Literal["prefect"]
    auth_setup_message_type: Literal["auth"]
    auth_success_message_type: Literal["auth_success"]
    first_application_frame_type: Literal["worker.hello.v1"]
    required_capabilities: tuple[WorkerChannelCapability, ...]
    optional_capabilities: tuple[WorkerChannelCapability, ...]
    supported_cleanup_kinds: tuple[CleanupKind, ...]
    scheduled_flow_run_acquisition: Literal["rest"]
    worker_startup_rollout: Literal["opportunistic_without_user_setting"]
    worker_side_cancellation_observation: Literal["event_subscription"]
    cleanup_delivery_guarantee: Literal[
        "at_least_once_one_active_reservation_per_message"
    ]
    cleanup_delivery_authority: Literal["reservation_token"]
    cloud_authorization_internals: Literal["excluded_from_shared_contract"]


WORK_POOL_WORKER_CHANNEL_CONTRACT = WorkerChannelContract(
    route=WORK_POOL_WORKER_CHANNEL_ROUTE,
    version=WORK_POOL_WORKER_CHANNEL_VERSION,
    websocket_subprotocol=WORKER_CHANNEL_SUBPROTOCOL,
    auth_setup_message_type="auth",
    auth_success_message_type="auth_success",
    first_application_frame_type="worker.hello.v1",
    required_capabilities=tuple(sorted(REQUIRED_WORKER_CHANNEL_CAPABILITIES)),
    optional_capabilities=tuple(sorted(OPTIONAL_WORKER_CHANNEL_CAPABILITIES)),
    supported_cleanup_kinds=SUPPORTED_CLEANUP_KINDS,
    scheduled_flow_run_acquisition="rest",
    worker_startup_rollout="opportunistic_without_user_setting",
    worker_side_cancellation_observation="event_subscription",
    cleanup_delivery_guarantee="at_least_once_one_active_reservation_per_message",
    cleanup_delivery_authority="reservation_token",
    cloud_authorization_internals="excluded_from_shared_contract",
)


class _StrictProtocolModel(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class WorkerChannelAuthRequest(_StrictProtocolModel):
    type: Literal["auth"]
    token: str | None = None


class WorkerChannelAuthSuccess(_StrictProtocolModel):
    type: Literal["auth_success"]


class WorkerChannelFrame(_StrictProtocolModel):
    type: WorkerChannelFrameType
    id: UUID
    sent_at: DateTime


class WorkerHelloPayload(_StrictProtocolModel):
    consumer_id: UUID
    worker_name: _NonEmptyString
    worker_type: _NonEmptyString
    heartbeat_interval_seconds: PositiveInteger
    supported_channel_versions: list[_NonEmptyString] = Field(min_length=1)
    requested_capabilities: list[_NonEmptyString] = Field(min_length=1)
    work_queue_names: list[_NonEmptyString] = Field(default_factory=list)
    handled_cleanup_kinds: list[CleanupKind] = Field(default_factory=list)
    max_cleanup_concurrency: NonNegativeInteger = 0
    create_pool_if_not_found: bool = False
    default_base_job_template: dict[str, Any] = Field(default_factory=dict)
    worker_metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def default_cleanup_concurrency(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "max_cleanup_concurrency" in data:
            return data

        requested = data.get("requested_capabilities", [])
        handled_cleanup_kinds = data.get("handled_cleanup_kinds", [])
        if not _is_non_string_iterable(requested) or not _is_non_string_iterable(
            handled_cleanup_kinds
        ):
            return data

        requested_values = tuple(requested)
        handled_cleanup_kind_values = tuple(handled_cleanup_kinds)
        normalized_data = {
            **data,
            "requested_capabilities": requested_values,
            "handled_cleanup_kinds": handled_cleanup_kind_values,
        }

        if (
            CLEANUP_DELIVERY_CAPABILITY in requested_values
            and handled_cleanup_kind_values
        ):
            return {**normalized_data, "max_cleanup_concurrency": 1}

        return normalized_data

    @model_validator(mode="after")
    def required_capabilities_are_requested(self) -> WorkerHelloPayload:
        requested = set(self.requested_capabilities)
        if not REQUIRED_WORKER_CHANNEL_CAPABILITIES.issubset(requested):
            missing = sorted(REQUIRED_WORKER_CHANNEL_CAPABILITIES - requested)
            raise ValueError(f"Missing required channel capabilities: {missing}")

        if CLEANUP_DELIVERY_CAPABILITY not in requested:
            if self.handled_cleanup_kinds:
                raise ValueError(
                    "`handled_cleanup_kinds` requires `cleanup_delivery.v1`"
                )
            if self.max_cleanup_concurrency:
                raise ValueError(
                    "`max_cleanup_concurrency` requires `cleanup_delivery.v1`"
                )

        return self


class WorkerHelloFrame(WorkerChannelFrame):
    type: Literal["worker.hello.v1"]
    payload: WorkerHelloPayload


class ResolvedWorkQueue(_StrictProtocolModel):
    id: UUID
    name: str = Field(min_length=1)


class WorkPoolSnapshot(WorkPool):
    id: UUID
    base_job_template: dict[str, Any]
    is_paused: bool
    storage_configuration: WorkPoolStorageConfiguration
    default_queue_id: UUID


class WorkPoolSnapshotPayload(_StrictProtocolModel):
    snapshot_sequence: PositiveInteger
    reason: str = Field(min_length=1)
    work_pool: WorkPoolSnapshot


class WorkerReadyPayload(_StrictProtocolModel):
    consumer_id: UUID
    worker_id: UUID | None
    selected_channel_version: WorkerChannelVersion
    effective_heartbeat_interval_seconds: PositiveInteger
    accepted_capabilities: list[WorkerChannelCapability] = Field(min_length=1)
    rejected_capabilities: list[_NonEmptyString] = Field(default_factory=list)
    effective_max_cleanup_concurrency: NonNegativeInteger = 0
    resolved_work_queues: list[ResolvedWorkQueue] = Field(default_factory=list)
    initial_snapshot: WorkPoolSnapshotPayload

    @model_validator(mode="after")
    def validate_capability_decision(self) -> WorkerReadyPayload:
        accepted = set(self.accepted_capabilities)
        rejected = set(self.rejected_capabilities)

        if overlap := accepted & rejected:
            raise ValueError(
                f"Capabilities cannot be both accepted and rejected: {sorted(overlap)}"
            )

        if not REQUIRED_WORKER_CHANNEL_CAPABILITIES.issubset(accepted):
            missing = sorted(REQUIRED_WORKER_CHANNEL_CAPABILITIES - accepted)
            raise ValueError(f"Missing accepted required capabilities: {missing}")

        if required_rejected := REQUIRED_WORKER_CHANNEL_CAPABILITIES & rejected:
            raise ValueError(
                f"Required capabilities cannot be rejected: {sorted(required_rejected)}"
            )

        if (
            CLEANUP_DELIVERY_CAPABILITY not in accepted
            and self.effective_max_cleanup_concurrency != 0
        ):
            raise ValueError(
                "`effective_max_cleanup_concurrency` must be 0 when "
                "`cleanup_delivery.v1` is unavailable"
            )

        if (
            CLEANUP_DELIVERY_CAPABILITY in accepted
            and self.effective_max_cleanup_concurrency == 0
        ):
            raise ValueError(
                "`effective_max_cleanup_concurrency` must be positive when "
                "`cleanup_delivery.v1` is accepted"
            )

        if self.initial_snapshot.reason != "initial":
            raise ValueError(
                "`worker.ready.v1` initial snapshot reason must be initial"
            )

        if self.initial_snapshot.snapshot_sequence != 1:
            raise ValueError("`worker.ready.v1` initial snapshot sequence must be 1")

        return self


class WorkerReadyFrame(WorkerChannelFrame):
    type: Literal["worker.ready.v1"]
    payload: WorkerReadyPayload


class WorkerHeartbeatPayload(_StrictProtocolModel):
    consumer_id: UUID
    worker_name: str = Field(min_length=1)
    heartbeat_interval_seconds: PositiveInteger


class WorkerHeartbeatFrame(WorkerChannelFrame):
    type: Literal["worker.heartbeat.v1"]
    payload: WorkerHeartbeatPayload


class WorkPoolSnapshotFrame(WorkerChannelFrame):
    type: Literal["work_pool.snapshot.v1"]
    payload: WorkPoolSnapshotPayload


class CancellingTimeoutTeardownTarget(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    flow_run_id: UUID
    infrastructure_pid: str | None = None


class PendingClaimTeardownTarget(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    flow_run_id: UUID
    claim_id: UUID
    execution_id: UUID | None = None
    infrastructure_pid: str | None = None


class _CleanupMessagePayloadBase(_StrictProtocolModel):
    message_id: UUID
    reservation_token: str = Field(min_length=1)
    lease_expires_at: DateTime
    delivery_count: PositiveInteger
    work_queue_id: UUID | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CancellingTimeoutCleanupMessagePayload(_CleanupMessagePayloadBase):
    kind: Literal["cancelling_timeout_teardown.v1"]
    target: CancellingTimeoutTeardownTarget


class PendingClaimCleanupMessagePayload(_CleanupMessagePayloadBase):
    kind: Literal["pending_claim_teardown.v1"]
    target: PendingClaimTeardownTarget


CleanupMessagePayload: TypeAlias = Annotated[
    Union[PendingClaimCleanupMessagePayload, CancellingTimeoutCleanupMessagePayload],
    Field(discriminator="kind"),
]


class CleanupMessageFrame(WorkerChannelFrame):
    type: Literal["cleanup.message.v1"]
    payload: CleanupMessagePayload


class CleanupOperationPayload(_StrictProtocolModel):
    message_id: UUID
    reservation_token: str = Field(min_length=1)


class CleanupReleasePayload(CleanupOperationPayload):
    reason: str = Field(min_length=1)


class CleanupAckFrame(WorkerChannelFrame):
    type: Literal["cleanup.ack.v1"]
    payload: CleanupOperationPayload


class CleanupReleaseFrame(WorkerChannelFrame):
    type: Literal["cleanup.release.v1"]
    payload: CleanupReleasePayload


class CleanupRenewFrame(WorkerChannelFrame):
    type: Literal["cleanup.renew.v1"]
    payload: CleanupOperationPayload


class CleanupOperationResultPayload(_StrictProtocolModel):
    request_frame_id: UUID
    message_id: UUID
    operation: CleanupOperation
    status: CleanupOperationStatus
    lease_expires_at: DateTime | None = None
    reason: str | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def validate_result_contract(self) -> CleanupOperationResultPayload:
        if self.status != "accepted" and not self.reason:
            raise ValueError(
                "`reason` is required for non-accepted cleanup operation results"
            )

        if self.lease_expires_at is not None and not (
            self.status == "accepted" and self.operation == "renew"
        ):
            raise ValueError(
                "`lease_expires_at` is only valid for accepted renew results"
            )

        if (
            self.status == "accepted"
            and self.operation == "renew"
            and self.lease_expires_at is None
        ):
            raise ValueError("Accepted renew results require `lease_expires_at`")

        return self


class CleanupOperationResultFrame(WorkerChannelFrame):
    type: Literal["cleanup.operation_result.v1"]
    payload: CleanupOperationResultPayload


WorkerChannelApplicationFrame: TypeAlias = Annotated[
    Union[
        WorkerHelloFrame,
        WorkerReadyFrame,
        WorkerHeartbeatFrame,
        WorkPoolSnapshotFrame,
        CleanupMessageFrame,
        CleanupAckFrame,
        CleanupReleaseFrame,
        CleanupRenewFrame,
        CleanupOperationResultFrame,
    ],
    Field(discriminator="type"),
]

WorkerChannelApplicationFrameAdapter: TypeAdapter[WorkerChannelApplicationFrame] = (
    TypeAdapter(WorkerChannelApplicationFrame)
)


def validate_worker_channel_frame(frame: Any) -> WorkerChannelApplicationFrame:
    return WorkerChannelApplicationFrameAdapter.validate_python(frame)


def select_worker_channel_version(
    supported_versions: Iterable[str],
) -> WorkerChannelVersion:
    if WORK_POOL_WORKER_CHANNEL_VERSION in set(supported_versions):
        return WORK_POOL_WORKER_CHANNEL_VERSION

    raise WorkerChannelProtocolError(
        WorkerChannelCloseReason.UNSUPPORTED_VERSION,
        "No mutually supported worker channel version",
    )


__all__ = [
    "CANCELLING_TIMEOUT_TEARDOWN",
    "CLEANUP_DELIVERY_CAPABILITY",
    "OPTIONAL_WORKER_CHANNEL_CAPABILITIES",
    "PENDING_CLAIM_TEARDOWN",
    "REQUIRED_WORKER_CHANNEL_CAPABILITIES",
    "SUPPORTED_CLEANUP_KINDS",
    "SUPPORTED_WORKER_CHANNEL_CAPABILITIES",
    "WORKER_CHANNEL_CLOSE_POLICIES",
    "WORKER_CHANNEL_SUBPROTOCOL",
    "WORKER_HEARTBEAT_CAPABILITY",
    "WORK_POOL_SNAPSHOT_CAPABILITY",
    "WORK_POOL_WORKER_CHANNEL_CONTRACT",
    "WORK_POOL_WORKER_CHANNEL_ROUTE",
    "WORK_POOL_WORKER_CHANNEL_VERSION",
    "CancellingTimeoutCleanupMessagePayload",
    "CancellingTimeoutTeardownTarget",
    "CleanupAckFrame",
    "CleanupKind",
    "CleanupMessageFrame",
    "CleanupMessagePayload",
    "CleanupOperationPayload",
    "CleanupOperationResultFrame",
    "CleanupOperationResultPayload",
    "CleanupOperationStatus",
    "CleanupReleaseFrame",
    "CleanupReleasePayload",
    "CleanupRenewFrame",
    "PendingClaimCleanupMessagePayload",
    "PendingClaimTeardownTarget",
    "ResolvedWorkQueue",
    "WorkerChannelApplicationFrame",
    "WorkerChannelApplicationFrameAdapter",
    "WorkerChannelAuthRequest",
    "WorkerChannelAuthSuccess",
    "WorkerChannelCapability",
    "WorkerChannelClosePolicy",
    "WorkerChannelCloseReason",
    "WorkerChannelContract",
    "WorkerChannelFrame",
    "WorkerChannelFrameType",
    "WorkerChannelProtocolError",
    "WorkerChannelVersion",
    "WorkerHeartbeatFrame",
    "WorkerHeartbeatPayload",
    "WorkerHelloFrame",
    "WorkerHelloPayload",
    "WorkerReadyFrame",
    "WorkerReadyPayload",
    "WorkPoolSnapshotFrame",
    "WorkPoolSnapshotPayload",
    "select_worker_channel_version",
    "validate_worker_channel_frame",
]
