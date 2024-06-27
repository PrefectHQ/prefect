"""
This module contains functions for validating job variables for deployments, work pools,
flow runs, and RunDeployment actions. These functions are used to validate that job
variables provided by users conform to the JSON schema defined in the work pool's base job
template.

Note some important details:

1. The order of applying job variables is: work pool's base job template, deployment, flow
   run. This means that flow run job variables override deployment job variables, which
   override work pool job variables.

2. The validation of job variables for work pools and deployments ignores required keys in
   because we don't know if the full set of overrides will include values for any required
   fields.

3.  Work pools can include default values for job variables. These can be normal types or
    references to blocks. We have not been validating these values or whether default blocks
    satisfy job variable JSON schemas. To avoid failing validation for existing (otherwise
    working) data, we ignore invalid defaults when validating deployment and flow run
    variables, but not when validating the work pool's base template, e.g. during work pool
    creation or updates. If we find defaults that are invalid, we have to ignore required
    fields when we run the full validation.

4. A flow run is the terminal point for job variables, so it is the only place where
   we validate required variables and default values. Thus,
   `validate_job_variables_for_deployment_flow_run` and
   `validate_job_variables_for_run_deployment_action` check for required fields.

5. We have been using Pydantic v1 to generate work pool base job templates, and it produces
   invalid JSON schemas for some fields, e.g. tuples and optional fields. We try to fix these
   schemas on the fly while validating job variables, but there is a case we can't resolve,
   which is whether or not an optional field supports a None value. In this case, we allow
   None values to be passed in, which means that if an optional field does not actually
   allow None values, the Pydantic model will fail to validate at runtime.
"""

from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

import pydantic
from fastapi import HTTPException, status
from sqlalchemy.exc import DBAPIError, NoInspectionAvailable
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.logging import get_logger
from prefect.server import models, schemas
from prefect.server.events.actions import RunDeployment
from prefect.server.schemas.core import Deployment, WorkPool
from prefect.utilities.schema_tools import ValidationError, is_valid_schema, validate

logger = get_logger("server.api.validation")

DeploymentAction = Union[
    schemas.actions.DeploymentCreate, schemas.actions.DeploymentUpdate
]
FlowRunAction = Union[
    schemas.actions.DeploymentFlowRunCreate, schemas.actions.FlowRunUpdate
]


async def _get_base_config_defaults(
    session: AsyncSession,
    base_config: dict,
    ignore_invalid_defaults: bool = True,
) -> Tuple[dict, bool]:
    variables_schema = base_config.get("variables", {})
    fields_schema: dict = variables_schema.get("properties", {})
    defaults: Dict[str, Any] = dict()
    has_invalid_defaults = False

    if not fields_schema:
        return defaults, has_invalid_defaults

    for variable_name, attrs in fields_schema.items():
        if "default" not in attrs:
            continue

        default = attrs["default"]

        if isinstance(default, dict) and "$ref" in default:
            hydrated_block = await _resolve_default_reference(default, session)
            if hydrated_block is None:
                continue
            defaults[variable_name] = hydrated_block
        else:
            defaults[variable_name] = default

        if ignore_invalid_defaults:
            errors = validate(
                {variable_name: defaults[variable_name]},
                variables_schema,
                raise_on_error=False,
                preprocess=False,
                ignore_required=True,
                allow_none_with_default=False,
            )
            if errors:
                has_invalid_defaults = True
                try:
                    del defaults[variable_name]
                except (IndexError, KeyError):
                    pass

    return defaults, has_invalid_defaults


async def _resolve_default_reference(
    variable: Dict[str, Any], session: AsyncSession
) -> Optional[Any]:
    """
    Resolve a reference to a block. The input variable should have a format of:

    {
        "$ref": {
            "block_document_id": "block_document_id"
        },
    }
    """
    if not isinstance(variable, dict):
        return None

    if "$ref" not in variable:
        return None

    reference_data = variable.get("$ref", {})
    if (provided_block_document_id := reference_data.get("block_document_id")) is None:
        return None

    if isinstance(provided_block_document_id, UUID):
        block_document_id = provided_block_document_id
    else:
        try:
            block_document_id = UUID(provided_block_document_id)
        except ValueError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found.")

    try:
        block_document = await models.block_documents.read_block_document_by_id(
            session, block_document_id
        )
    except pydantic.ValidationError:
        # It's possible to get an invalid UUID here because the block document ID is
        # not validated by our schemas.
        logger.info("Could not find block document with ID %s", block_document_id)
        block_document = None

    if not block_document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found.")

    return block_document.data


async def _validate_work_pool_job_variables(
    session: AsyncSession,
    work_pool_name: str,
    base_job_template: Dict[str, Any],
    *job_vars: Dict[str, Any],
    ignore_required: bool = True,
    ignore_invalid_defaults: bool = True,
    raise_on_error=True,
) -> None:
    if not base_job_template:
        logger.info(
            "Cannot validate job variables for work pool %s because it does not have a base job template",
            work_pool_name,
        )
        return

    variables_schema = base_job_template.get("variables")
    if not variables_schema:
        logger.info(
            "Cannot validate job variables for work pool %s "
            "because it does not specify a variables schema",
            work_pool_name,
        )
        return

    try:
        is_valid_schema(variables_schema, preprocess=False)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    base_vars, invalid_defaults = await _get_base_config_defaults(
        session, base_job_template, ignore_invalid_defaults
    )
    all_job_vars = {**base_vars}

    for jvs in job_vars:
        if isinstance(jvs, dict):
            all_job_vars.update(jvs)

    # If we are ignoring validation for default values and there were invalid defaults,
    # then we can't check for required fields because we won't have the default values
    # to satisfy nissing required fields.
    should_ignore_required = ignore_required or (
        ignore_invalid_defaults and invalid_defaults
    )

    validate(
        all_job_vars,
        variables_schema,
        raise_on_error=raise_on_error,
        preprocess=True,
        ignore_required=should_ignore_required,
        # We allow None values to be passed in for optional fields if there is a default
        # value for the field. This is because we have blocks that contain default None
        # values that will fail to validate otherwise. However, this means that if an
        # optional field does not actually allow None values, the Pydantic model will fail
        # to validate at runtime. Unfortunately, there is not a good solution to this
        # problem at this time.
        allow_none_with_default=True,
    )


async def validate_job_variables_for_deployment_flow_run(
    session: AsyncSession,
    deployment: Deployment,
    flow_run: FlowRunAction,
) -> None:
    """
    Validate job variables for a flow run created for a deployment.

    Flow runs are the terminal point for job variable overlays, so we validate required
    job variables because all variables should now be present.
    """
    # If we aren't able to access a deployment's work pool, we don't have a base job
    # template to validate job variables against. This is not a validation failure because
    # some deployments may not have a work pool, such as those created by flow.serve().
    if deployment.work_queue is None or deployment.work_queue.work_pool is None:
        logger.info(
            "Cannot validate job variables for deployment %s "
            "because it does not have a work pool",
            deployment.id,
        )
        return

    work_pool = deployment.work_queue.work_pool

    try:
        await _validate_work_pool_job_variables(
            session,
            work_pool.name,
            work_pool.base_job_template,
            deployment.job_variables or {},
            flow_run.job_variables or {},
            ignore_required=False,
            ignore_invalid_defaults=True,
        )
    except ValidationError as exc:
        if isinstance(flow_run, schemas.actions.DeploymentFlowRunCreate):
            error_msg = f"Error creating flow run: {exc}"
        else:
            error_msg = f"Error updating flow run: {exc}"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


async def validate_job_variables_for_deployment(
    session: AsyncSession,
    work_pool: WorkPool,
    deployment: DeploymentAction,
) -> None:
    """
    Validate job variables for deployment creation and updates.

    This validation applies only to deployments that have a work pool. If the deployment
    does not have a work pool, we cannot validate job variables because we don't have a
    base job template to validate against, so we skip this validation.

    Unlike validations for flow runs, validation here ignores required keys in the schema
    because we don't know if the full set of overrides will include values for any
    required fields. If the full set of job variables when a flow is running, including
    the deployment's and flow run's overrides, fails to specify a value for the required
    key, that's an error.
    """
    if not deployment.job_variables:
        return
    try:
        await _validate_work_pool_job_variables(
            session,
            work_pool.name,
            work_pool.base_job_template,
            deployment.job_variables or {},
            ignore_required=True,
            ignore_invalid_defaults=True,
        )
    except ValidationError as exc:
        if isinstance(deployment, schemas.actions.DeploymentCreate):
            error_msg = f"Error creating deployment: {exc}"
        else:
            error_msg = f"Error updating deployment: {exc}"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


async def validate_job_variable_defaults_for_work_pool(
    session: AsyncSession,
    work_pool_name: str,
    base_job_template: Dict[str, Any],
) -> None:
    """
    Validate the default job variables for a work pool.

    This validation checks that default values for job variables match the JSON schema
    defined in the work pool's base job template. It also resolves references to block
    documents in the default values and hydrates them to perform the validation.

    Unlike validations for flow runs, validation here ignores required keys in the schema
    because we're only concerned with default values. The absence of a default for a
    required field is not an error, but if the full set of job variables when a flow is
    running, including the deployment's and flow run's overrides, fails to specify a value
    for the required key, that's an error.

    NOTE: This will raise an HTTP 404 error if a referenced block document does not exist.
    """
    try:
        await _validate_work_pool_job_variables(
            session,
            work_pool_name,
            base_job_template,
            ignore_required=True,
            ignore_invalid_defaults=False,
        )
    except ValidationError as exc:
        error_msg = f"Validation failed for work pool's job variable defaults: {exc}"
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)


async def validate_job_variables_for_run_deployment_action(
    session: AsyncSession,
    run_action: RunDeployment,
) -> None:
    """
    Validate the job variables for a RunDeployment action.

    This action is equivalent to creating a flow run for a deployment, so we validate
    required job variables because all variables should now be present.
    """
    try:
        deployment = await models.deployments.read_deployment(
            session, run_action.deployment_id
        )
    except (DBAPIError, NoInspectionAvailable):
        # It's possible to get an invalid UUID here because the deployment ID is
        # not validated by our schemas.
        logger.info("Could not find deployment with ID %s", run_action.deployment_id)
        deployment = None
    if not deployment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Deployment not found.")

    if deployment.work_queue is None or deployment.work_queue.work_pool is None:
        logger.info(
            "Cannot validate job variables for deployment %s "
            "because it does not have a work pool",
            run_action.deployment_id,
        )
        return

    if not (deployment.job_variables or run_action.job_variables):
        return

    work_pool = deployment.work_queue.work_pool

    await _validate_work_pool_job_variables(
        session,
        work_pool.name,
        work_pool.base_job_template,
        run_action.job_variables or {},
        ignore_required=False,
        ignore_invalid_defaults=True,
    )
