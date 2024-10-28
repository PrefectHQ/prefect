import time
from collections import defaultdict
from typing import Dict, List, Set

from pydantic import BaseModel
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import TypeAlias

TaskKey: TypeAlias = str
WorkerId: TypeAlias = str


class TaskWorkerResponse(BaseModel):
    identifier: WorkerId
    task_keys: List[TaskKey]
    timestamp: DateTime


class InMemoryTaskWorkerTracker:
    def __init__(self) -> None:
        self.workers: dict[WorkerId, Set[TaskKey]] = {}
        self.task_keys: Dict[TaskKey, Set[WorkerId]] = defaultdict(set)
        self.worker_timestamps: Dict[WorkerId, float] = {}

    async def observe_worker(
        self,
        task_keys: List[TaskKey],
        worker_id: WorkerId,
    ) -> None:
        self.workers[worker_id] = self.workers.get(worker_id, set()) | set(task_keys)
        self.worker_timestamps[worker_id] = time.monotonic()

        for task_key in task_keys:
            self.task_keys[task_key].add(worker_id)

    async def forget_worker(
        self,
        worker_id: WorkerId,
    ) -> None:
        if worker_id in self.workers:
            task_keys = self.workers.pop(worker_id)
            for task_key in task_keys:
                self.task_keys[task_key].discard(worker_id)
                if not self.task_keys[task_key]:
                    del self.task_keys[task_key]
        self.worker_timestamps.pop(worker_id, None)

    async def get_workers_for_task_keys(
        self,
        task_keys: List[TaskKey],
    ) -> List[TaskWorkerResponse]:
        if not task_keys:
            return await self.get_all_workers()
        active_workers = set().union(*(self.task_keys[key] for key in task_keys))
        return [self._create_worker_response(worker_id) for worker_id in active_workers]

    async def get_all_workers(self) -> List[TaskWorkerResponse]:
        return [
            self._create_worker_response(worker_id)
            for worker_id in self.worker_timestamps.keys()
        ]

    def _create_worker_response(self, worker_id: WorkerId) -> TaskWorkerResponse:
        timestamp = time.monotonic() - self.worker_timestamps[worker_id]
        return TaskWorkerResponse(
            identifier=worker_id,
            task_keys=list(self.workers.get(worker_id, set())),
            timestamp=DateTime.utcnow().subtract(seconds=timestamp),
        )

    def reset(self) -> None:
        """Testing utility to reset the state of the task worker tracker"""
        self.workers.clear()
        self.task_keys.clear()
        self.worker_timestamps.clear()


# Global instance of the task worker tracker
task_worker_tracker = InMemoryTaskWorkerTracker()


# Main utilities to be used in the API layer
async def observe_worker(
    task_keys: List[TaskKey],
    worker_id: WorkerId,
) -> None:
    await task_worker_tracker.observe_worker(task_keys, worker_id)


async def forget_worker(
    worker_id: WorkerId,
) -> None:
    await task_worker_tracker.forget_worker(worker_id)


async def get_workers_for_task_keys(
    task_keys: List[TaskKey],
) -> List[TaskWorkerResponse]:
    return await task_worker_tracker.get_workers_for_task_keys(task_keys)


async def get_all_workers() -> List[TaskWorkerResponse]:
    return await task_worker_tracker.get_all_workers()
