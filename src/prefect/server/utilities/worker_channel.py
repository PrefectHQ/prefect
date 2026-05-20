from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.logging import get_logger
from prefect.server.utilities import messaging
from prefect.types import DateTime
from prefect.types._datetime import now

logger: logging.Logger = get_logger("prefect.server.utilities.worker_channel")

WORKER_CHANNEL_SNAPSHOT_TOPIC = "work-pool-worker-channel-snapshots"

WORK_POOL_FIELDS_THAT_TRIGGER_SNAPSHOTS = frozenset(
    {
        "base_job_template",
        "concurrency_limit",
        "is_paused",
        "storage_configuration",
    }
)


class WorkerChannelSnapshotInvalidation(PrefectBaseModel):
    work_pool_id: UUID
    reason: str
    work_pool_deleted: bool = False
    published_at: DateTime | None = None

    def targets(
        self,
        *,
        work_pool_id: UUID,
        subscribed_after: DateTime | None = None,
    ) -> bool:
        if subscribed_after is not None:
            if self.published_at is None or self.published_at < subscribed_after:
                return False

        return self.work_pool_id == work_pool_id


def work_pool_update_triggers_snapshot(update_values: Mapping[str, Any]) -> bool:
    return bool(WORK_POOL_FIELDS_THAT_TRIGGER_SNAPSHOTS.intersection(update_values))


async def publish_snapshot_invalidation(
    invalidation: WorkerChannelSnapshotInvalidation,
) -> None:
    try:
        if invalidation.published_at is None:
            invalidation = invalidation.model_copy(update={"published_at": now("UTC")})

        async with messaging.create_publisher(
            topic=WORKER_CHANNEL_SNAPSHOT_TOPIC
        ) as publisher:
            await publisher.publish_data(
                invalidation.model_dump_json().encode(),
                attributes={
                    "work_pool_id": str(invalidation.work_pool_id),
                    "reason": invalidation.reason,
                },
            )
    except Exception:
        logger.warning(
            "Failed to publish worker channel snapshot invalidation",
            exc_info=True,
        )


def parse_snapshot_invalidation(
    message: messaging.Message,
) -> WorkerChannelSnapshotInvalidation:
    data = message.data.encode() if isinstance(message.data, str) else message.data
    return WorkerChannelSnapshotInvalidation.model_validate_json(data)
