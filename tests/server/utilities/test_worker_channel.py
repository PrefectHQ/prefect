from typing import Any
from uuid import uuid4

import pytest

from prefect.server.utilities import worker_channel


class TestSnapshotInvalidations:
    async def test_publish_snapshot_invalidation_propagates_broker_failure(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class FailingPublisher:
            async def __aenter__(self) -> "FailingPublisher":
                return self

            async def __aexit__(self, *exc_info: Any) -> bool:
                return False

            async def publish_data(
                self, data: bytes, attributes: dict[str, str]
            ) -> None:
                raise RuntimeError("broker unavailable")

        def create_publisher(topic: str) -> FailingPublisher:
            return FailingPublisher()

        monkeypatch.setattr(
            worker_channel.messaging,
            "create_publisher",
            create_publisher,
        )

        with pytest.raises(RuntimeError, match="broker unavailable"):
            await worker_channel.publish_snapshot_invalidation(
                worker_channel.WorkerChannelSnapshotInvalidation(
                    work_pool_id=uuid4(),
                    reason="work_pool_updated",
                )
            )

    def test_snapshot_invalidation_targets_work_pool(self) -> None:
        work_pool_id = uuid4()
        invalidation = worker_channel.WorkerChannelSnapshotInvalidation(
            work_pool_id=work_pool_id,
            reason="work_pool_updated",
        )

        assert invalidation.targets(work_pool_id=work_pool_id)
        assert not invalidation.targets(work_pool_id=uuid4())
