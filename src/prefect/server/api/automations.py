from typing import Optional, Sequence
from uuid import UUID

import pendulum
from fastapi import Body, Depends, HTTPException, Path, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from prefect.server.api.dependencies import LimitBody
from prefect.server.api.validation import (
    validate_job_variables_for_run_deployment_action,
)
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import actions
from prefect.server.events.filters import AutomationFilter, AutomationFilterCreated
from prefect.server.events.models import automations as automations_models
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationCreate,
    AutomationPartialUpdate,
    AutomationSort,
    AutomationUpdate,
)
from prefect.server.exceptions import ObjectNotFoundError
from prefect.server.utilities.server import PrefectRouter
from prefect.utilities.schema_tools.validation import (
    ValidationError as JSONSchemaValidationError,
)

router = PrefectRouter(
    prefix="/automations",
    tags=["Automations"],
    dependencies=[],
)


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_automation(
    automation: AutomationCreate,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Automation:
    # reset any client-provided IDs on the provided triggers
    automation.trigger.reset_ids()

    errors = []
    for action in automation.actions:
        if (
            isinstance(action, actions.RunDeployment)
            and action.deployment_id is not None
            and action.job_variables is not None
            and action.job_variables != {}
        ):
            async with db.session_context() as session:
                try:
                    await validate_job_variables_for_run_deployment_action(
                        session, action
                    )
                except JSONSchemaValidationError as exc:
                    errors.append(str(exc))

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error creating automation: {' '.join(errors)}",
        )

    automation_dict = automation.model_dump()
    owner_resource = automation_dict.pop("owner_resource", None)

    async with db.session_context(begin_transaction=True) as session:
        created_automation = await automations_models.create_automation(
            session=session,
            automation=Automation(
                **automation_dict,
            ),
        )

        if owner_resource:
            await automations_models.relate_automation_to_resource(
                session,
                automation_id=created_automation.id,
                resource_id=owner_resource,
                owned_by_resource=True,
            )

    return created_automation


@router.put("/{id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def update_automation(
    automation: AutomationUpdate,
    automation_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    # reset any client-provided IDs on the provided triggers
    automation.trigger.reset_ids()

    errors = []
    for action in automation.actions:
        if (
            isinstance(action, actions.RunDeployment)
            and action.deployment_id is not None
            and action.job_variables is not None
        ):
            async with db.session_context() as session:
                try:
                    await validate_job_variables_for_run_deployment_action(
                        session, action
                    )
                except JSONSchemaValidationError as exc:
                    errors.append(str(exc))
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error creating automation: {' '.join(errors)}",
        )

    async with db.session_context(begin_transaction=True) as session:
        updated = await automations_models.update_automation(
            session=session,
            automation_update=automation,
            automation_id=automation_id,
        )

    if not updated:
        raise ObjectNotFoundError("Automation not found")


@router.patch(
    "/{id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def patch_automation(
    automation: AutomationPartialUpdate,
    automation_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    try:
        async with db.session_context(begin_transaction=True) as session:
            updated = await automations_models.update_automation(
                session=session,
                automation_update=automation,
                automation_id=automation_id,
            )
    except ValidationError as e:
        raise RequestValidationError(
            errors=e.errors(),
            body=automation.model_dump(mode="json"),
        )

    if not updated:
        raise ObjectNotFoundError("Automation not found")


@router.delete(
    "/{id:uuid}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_automation(
    automation_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        deleted = await automations_models.delete_automation(
            session=session,
            automation_id=automation_id,
        )

    if not deleted:
        raise ObjectNotFoundError("Automation not found")


@router.post("/filter")
async def read_automations(
    sort: AutomationSort = Body(AutomationSort.NAME_ASC),
    limit: int = LimitBody(),
    offset: int = Body(0, ge=0),
    automations: Optional[AutomationFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Sequence[Automation]:
    async with db.session_context() as session:
        return await automations_models.read_automations_for_workspace(
            session=session,
            sort=sort,
            limit=limit,
            offset=offset,
            automation_filter=automations,
        )


@router.post("/count")
async def count_automations(
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> int:
    async with db.session_context() as session:
        return await automations_models.count_automations_for_workspace(session=session)


@router.get("/{id:uuid}")
async def read_automation(
    automation_id: UUID = Path(..., alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Automation:
    async with db.session_context() as session:
        automation = await automations_models.read_automation(
            session=session,
            automation_id=automation_id,
        )

    if not automation:
        raise ObjectNotFoundError("Automation not found")
    return automation


@router.get("/related-to/{resource_id:str}")
async def read_automations_related_to_resource(
    resource_id: str = Path(..., alias="resource_id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> Sequence[Automation]:
    async with db.session_context() as session:
        return await automations_models.read_automations_related_to_resource(
            session=session,
            resource_id=resource_id,
        )


@router.delete("/owned-by/{resource_id:str}", status_code=status.HTTP_202_ACCEPTED)
async def delete_automations_owned_by_resource(
    resource_id: str = Path(..., alias="resource_id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
):
    async with db.session_context(begin_transaction=True) as session:
        await automations_models.delete_automations_owned_by_resource(
            session,
            resource_id=resource_id,
            automation_filter=AutomationFilter(
                created=AutomationFilterCreated(before_=pendulum.now("UTC"))
            ),
        )
