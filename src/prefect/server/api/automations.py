from typing import Optional, Sequence
from uuid import UUID

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.server.events.filters import AutomationFilter, AutomationFilterCreated

if HAS_PYDANTIC_V2:
    from pydantic.v1 import ValidationError
    from pydantic.v1.error_wrappers import ErrorWrapper
else:
    from pydantic import ValidationError
    from pydantic.error_wrappers import ErrorWrapper

from prefect._vendor.fastapi import Body, Depends, HTTPException, Path, status
from prefect._vendor.fastapi.exceptions import RequestValidationError

from prefect._internal.schemas.validators import validate_values_conform_to_schema
from prefect.server.api.clients import OrchestrationClient, WorkPoolsOrchestrationClient
from prefect.server.api.dependencies import LimitBody
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import actions
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
from prefect.settings import (
    PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    PREFECT_EXPERIMENTAL_EVENTS,
)


def automations_enabled() -> bool:
    if not PREFECT_EXPERIMENTAL_EVENTS or not PREFECT_API_SERVICES_TRIGGERS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automations are not enabled. Please enable the"
            " PREFECT_EXPERIMENTAL_EVENTS and"
            " PREFECT_API_SERVICES_TRIGGERS_ENABLED settings.",
        )


router = PrefectRouter(
    prefix="/automations",
    tags=["Automations"],
    dependencies=[Depends(automations_enabled)],
)


class FlowRunInfrastructureMissing(Exception):
    """
    Raised when there is an missing infrastructure data when creating or updating a
    flow run.
    """


def _get_base_config_defaults(base_config: dict):
    template: dict = base_config.get("variables", {}).get("properties", {})
    defaults = dict()
    for variable_name, attrs in template.items():
        if "default" in attrs:
            defaults[variable_name] = attrs["default"]

    return defaults


async def _validate_run_deployment_action_against_pool_schema(
    *,
    deployment_id: UUID,
    job_variables: dict,
):
    async with OrchestrationClient() as oc:
        deployment = await oc.read_deployment(deployment_id=deployment_id)
        if deployment is None:
            raise FlowRunInfrastructureMissing(
                f"Deployment {deployment_id} for RunDeployment action not found"
            )
        if not deployment.work_pool_name:
            raise FlowRunInfrastructureMissing(
                f"Deployment {deployment_id} has no work pool name"
            )

    async with WorkPoolsOrchestrationClient() as wpc:
        work_pool = await wpc.read_work_pool(deployment.work_pool_name)

    default_vars = _get_base_config_defaults(work_pool.base_job_template)
    deployment_vars = deployment.job_variables or {}
    validate_values_conform_to_schema(
        {**default_vars, **deployment_vars, **job_variables},
        work_pool.base_job_template.get("variables", {}),
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
            try:
                await _validate_run_deployment_action_against_pool_schema(
                    deployment_id=action.deployment_id,
                    job_variables=action.job_variables,
                )
            except (ValueError, FlowRunInfrastructureMissing) as exc:
                errors.append(str(exc))

        if errors:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Error creating automation: {' '.join(errors)}",
            )

    automation_dict = automation.dict()
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
            try:
                await _validate_run_deployment_action_against_pool_schema(
                    deployment_id=action.deployment_id,
                    job_variables=action.job_variables,
                )
            except ValueError as exc:
                errors.append(str(exc))
            except AssertionError:
                errors.append(
                    "Unable to find required resources for automation update."
                )
        if errors:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
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
            errors=[ErrorWrapper(e, "automation")],
            body=automation.dict(json_compatible=True),
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
