from typing import List, Optional

from fastapi import Body
from pydantic import BaseModel

from prefect.server import models
from prefect.server.models.task_workers import TaskWorkerResponse
from prefect.server.utilities.server import PrefectRouter

router: PrefectRouter = PrefectRouter(prefix="/task_workers", tags=["Task Workers"])


class TaskWorkerFilter(BaseModel):
    task_keys: List[str]


@router.post("/filter")
async def read_task_workers(
    task_worker_filter: Optional[TaskWorkerFilter] = Body(
        default=None, description="The task worker filter", embed=True
    ),
) -> List[TaskWorkerResponse]:
    """
    Read active task workers. Optionally filter by task keys.

    For more information, see https://docs.prefect.io/v3/develop/deferred-tasks.
    """

    if task_worker_filter and task_worker_filter.task_keys:
        return await models.task_workers.get_workers_for_task_keys(
            task_keys=task_worker_filter.task_keys,
        )

    else:
        return await models.task_workers.get_all_workers()
