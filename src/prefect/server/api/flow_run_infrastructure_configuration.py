"""
Routes for interacting with flow run infrastructure configuration objects.
"""

from typing import List
from uuid import UUID

from fastapi import Body, Depends, HTTPException, Path, Response, status

import prefect.server.api.dependencies as dependencies
import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import PrefectRouter

router = PrefectRouter(
    prefix="/flow_run_infrastructure_configuration",
    tags=["Flow Run Infrastructure Configuration"],
)


@router.post("/")
async def create_flow_run_infrastructure_configuration(
    flow_run_id: UUID,
    job_configuration: dict,
    db: PrefectDBInterface = Depends(provide_database_interface),
    response: Response = None,
) -> schemas.responses.FlowRunResponse:
    """
    Create a flow run infrastructure configuration.
    """

    async with db.session_context(begin_transaction=True) as session:
        flow_run = await models.flow_runs.read_flow_run(
            session=session,
            flow_run_id=flow_run_id,
        )

        if not flow_run:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Flow run not found.")

        model = await models.flow_run.create_flow_run_infrastructure_configuration(
            session=session,
            flow_run_id=flow_run_id,
            job_configuration=job_configuration,
        )

        return (
            schemas.responses.FlowRunInfrastructureConfigurationResponse.model_validate(
                model, from_attributes=True
            )
        )
