from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import Body, Depends
from pydantic import Field, field_validator

from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.schemas.states import StateType
from prefect.server.utilities.database import UUID as UUIDTypeDecorator
from prefect.server.utilities.schemas import PrefectBaseModel
from prefect.server.utilities.server import PrefectRouter
from prefect.types import DateTime
from prefect.types._datetime import create_datetime_instance, parse_datetime

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger()

router: PrefectRouter = PrefectRouter(prefix="/ui/flows", tags=["Flows", "UI"])


class SimpleNextFlowRun(PrefectBaseModel):
    id: UUID = Field(default=..., description="The flow run id.")
    flow_id: UUID = Field(default=..., description="The flow id.")
    name: str = Field(default=..., description="The flow run name")
    state_name: str = Field(default=..., description="The state name.")
    state_type: StateType = Field(default=..., description="The state type.")
    next_scheduled_start_time: DateTime = Field(
        default=..., description="The next scheduled start time"
    )

    @field_validator("next_scheduled_start_time", mode="before")
    @classmethod
    def validate_next_scheduled_start_time(cls, v: DateTime | datetime) -> DateTime:
        if isinstance(v, datetime):
            return create_datetime_instance(v)
        return v


@router.post("/count-deployments")
async def count_deployments_by_flow(
    flow_ids: List[UUID] = Body(default=..., embed=True, max_items=200),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Dict[UUID, int]:
    """
    Get deployment counts by flow id.
    """
    async with db.session_context() as session:
        query = (
            sa.select(
                db.Deployment.flow_id,
                sa.func.count(db.Deployment.id).label("deployment_count"),
            )
            .where(db.Deployment.flow_id.in_(flow_ids))
            .group_by(db.Deployment.flow_id)
        )

        results = await session.execute(query)

        deployment_counts_by_flow = {
            flow_id: deployment_count for flow_id, deployment_count in results.all()
        }

        return {
            flow_id: deployment_counts_by_flow.get(flow_id, 0) for flow_id in flow_ids
        }


def _get_postgres_next_runs_query(flow_ids: List[UUID]):
    # Here we use the raw query because CROSS LATERAL JOINS are very
    # difficult to express correctly in sqlalchemy.
    raw_query = sa.text(
        """
        SELECT fr.id, fr.name, fr.flow_id, fr.state_name, fr.state_type, fr.state_name, fr.next_scheduled_start_time
        FROM (
            SELECT DISTINCT flow_id FROM flow_run
            WHERE flow_id IN :flow_ids
            AND state_type = 'SCHEDULED'
            ) AS unique_flows
        CROSS JOIN LATERAL (
            SELECT *
            FROM flow_run fr
            WHERE fr.flow_id = unique_flows.flow_id
            AND fr.state_type = 'SCHEDULED'
            ORDER BY fr.next_scheduled_start_time ASC
            LIMIT 1
        ) fr;
        """
    )

    bindparams = [
        sa.bindparam(
            "flow_ids",
            flow_ids,
            expanding=True,
            type_=UUIDTypeDecorator,
        ),
    ]

    query = raw_query.bindparams(*bindparams)
    return query


def _get_sqlite_next_runs_query(flow_ids: List[UUID]):
    raw_query = sa.text(
        """
        WITH min_times AS (
            SELECT flow_id, MIN(next_scheduled_start_time) AS min_next_scheduled_start_time
            FROM flow_run
            WHERE flow_id IN :flow_ids
            AND state_type = 'SCHEDULED'
            GROUP BY flow_id
        )
        SELECT fr.id, fr.name, fr.flow_id, fr.state_name, fr.state_type, fr.next_scheduled_start_time
        FROM flow_run fr
        JOIN min_times mt ON fr.flow_id = mt.flow_id AND fr.next_scheduled_start_time = mt.min_next_scheduled_start_time
        WHERE fr.state_type = 'SCHEDULED';

        """
    )

    bindparams = [
        sa.bindparam(
            "flow_ids",
            flow_ids,
            expanding=True,
            type_=UUIDTypeDecorator,
        ),
    ]

    query = raw_query.bindparams(*bindparams)
    return query


@router.post("/next-runs")
async def next_runs_by_flow(
    flow_ids: List[UUID] = Body(default=..., embed=True, max_items=200),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Dict[UUID, Optional[SimpleNextFlowRun]]:
    """
    Get the next flow run by flow id.
    """

    async with db.session_context() as session:
        if db.dialect.name == "postgresql":
            query = _get_postgres_next_runs_query(flow_ids=flow_ids)
        else:
            query = _get_sqlite_next_runs_query(flow_ids=flow_ids)

        results = await session.execute(query)

        results_by_flow_id = {
            UUID(str(result.flow_id)): SimpleNextFlowRun(
                id=result.id,
                flow_id=result.flow_id,
                name=result.name,
                state_name=result.state_name,
                state_type=result.state_type,
                next_scheduled_start_time=parse_datetime(
                    result.next_scheduled_start_time
                ).replace(tzinfo=ZoneInfo("UTC"))
                if isinstance(result.next_scheduled_start_time, str)
                else result.next_scheduled_start_time,
            )
            for result in results.all()
        }

        response = {
            flow_id: results_by_flow_id.get(flow_id, None) for flow_id in flow_ids
        }
        return response
