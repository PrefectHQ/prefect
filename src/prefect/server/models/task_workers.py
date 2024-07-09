import time
from typing import Dict, List

from cachetools import TTLCache
from pydantic import BaseModel
from pydantic_extra_types.pendulum_dt import DateTime
from typing_extensions import TypeAlias

from prefect.settings import PREFECT_TASK_WORKER_ACTIVITY_TIMEOUT

TaskKey: TypeAlias = str
WorkerId: TypeAlias = str


class TaskWorkerResponse(BaseModel):
    identifier: WorkerId
    task_keys: List[TaskKey]
    timestamp: DateTime


class InMemoryTaskWorkerTracker:
    def __init__(
        self,
        maxsize: int = 1000,
        ttl: float = PREFECT_TASK_WORKER_ACTIVITY_TIMEOUT.value(),
    ):
        self.workers: TTLCache[WorkerId, set[TaskKey]] = TTLCache(
            maxsize=maxsize, ttl=ttl
        )
        self.task_keys: Dict[TaskKey, Dict[WorkerId, float]] = {}

    async def observe_worker(
        self,
        task_keys: List[TaskKey],
        worker_id: WorkerId,
    ) -> None:
        now = time.monotonic()

        if worker_id not in self.workers:
            self.workers[worker_id] = set()
        self.workers[worker_id].update(task_keys)

        for task_key in task_keys:
            if task_key not in self.task_keys:
                self.task_keys[task_key] = {}
            self.task_keys[task_key][worker_id] = now

        # Update the TTL for this worker
        self.workers.__setitem__(worker_id, self.workers[worker_id])

    async def forget_worker(
        self,
        worker_id: WorkerId,
    ) -> None:
        if worker_id in self.workers:
            task_keys = self.workers[worker_id]
            del self.workers[worker_id]

            for task_key in task_keys:
                if task_key in self.task_keys:
                    self.task_keys[task_key].pop(worker_id, None)

    def _create_worker_response(
        self, worker_id: WorkerId, task_keys: set[TaskKey]
    ) -> TaskWorkerResponse:
        return TaskWorkerResponse(
            identifier=worker_id,
            task_keys=list(task_keys),
            timestamp=DateTime.utcnow(),
        )

    async def get_workers_for_task_keys(
        self,
        task_keys: List[TaskKey],
    ) -> List[TaskWorkerResponse]:
        active_workers = set()

        for task_key in task_keys:
            if task_key in self.task_keys:
                active_workers.update(
                    worker_id
                    for worker_id in self.task_keys[task_key]
                    if worker_id in self.workers
                )

        return [
            self._create_worker_response(worker_id, self.workers[worker_id])
            for worker_id in active_workers
        ]

    async def get_all_workers(self) -> List[TaskWorkerResponse]:
        return [
            self._create_worker_response(worker_id, task_keys)
            for worker_id, task_keys in self.workers.items()
        ]


# Global instance of the task worker tracker
task_worker_tracker = InMemoryTaskWorkerTracker()


# API functions
async def observe_worker(
    task_keys: List[TaskKey],
    worker_id: WorkerId,
) -> None:
    await task_worker_tracker.observe_worker(task_keys, worker_id)


async def forget_worker(
    worker_id: WorkerId,
) -> None:
    print(f"Forgetting worker {worker_id!r}")
    await task_worker_tracker.forget_worker(worker_id)


async def get_workers_for_task_keys(
    task_keys: List[TaskKey],
) -> List[TaskWorkerResponse]:
    return await task_worker_tracker.get_workers_for_task_keys(task_keys)


async def get_all_workers() -> List[TaskWorkerResponse]:
    return await task_worker_tracker.get_all_workers()
