from typing import List

from prefect.logging import get_logger
from prefect.orion import models
from prefect.orion.utilities.server import OrionRouter

logger = get_logger("orion.api.ui.flags")

router = OrionRouter(prefix="/ui/flow_runs", tags=["Flow Runs", "UI"])


@router.post("/flags")
async def read_flow_run_history() -> List[str]:
    async with db.session_context() as session:
        result = await models.flow_runs.read_flow_runs(
            columns=columns,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
            sort=sort,
            limit=limit,
            offset=offset,
            session=session,
        )
    return [
        SimpleFlowRun(
            id=r.id,
            state_type=r.state_type,
            timestamp=r.start_time or r.expected_start_time,
            duration=r.estimated_run_time,
            lateness=r.estimated_start_time_delta,
        )
        for r in result
    ]
