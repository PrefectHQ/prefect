from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.logging import get_logger
from prefect.server.utilities import messaging

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
WORK_QUEUE_FIELDS_THAT_TRIGGER_SNAPSHOTS = frozenset(
    {
        "concurrency_limit",
        "is_paused",
        "name",
        "priority",
    }
)


class WorkerChannelSnapshotInvalidation(PrefectBaseModel):
    work_pool_id: UUID
    reason: str
    work_queue_id: UUID | None = None
    work_pool_deleted: bool = False

    def targets(
        self,
        *,
        work_pool_id: UUID,
        selected_work_queue_ids: frozenset[UUID] | None,
    ) -> bool:
        if self.work_pool_id != work_pool_id:
            return False

        if self.work_queue_id is None or selected_work_queue_ids is None:
            return True

        return self.work_queue_id in selected_work_queue_ids


def work_pool_update_triggers_snapshot(update_values: Mapping[str, Any]) -> bool:
    return bool(WORK_POOL_FIELDS_THAT_TRIGGER_SNAPSHOTS.intersection(update_values))


def work_queue_update_triggers_snapshot(update_values: Mapping[str, Any]) -> bool:
    return bool(WORK_QUEUE_FIELDS_THAT_TRIGGER_SNAPSHOTS.intersection(update_values))


async def publish_snapshot_invalidation(
    invalidation: WorkerChannelSnapshotInvalidation,
) -> None:
    try:
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
