from typing import Any, Dict, Union

from prefect._vendor.fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.utilities.schema_tools import ValidationError, validate


def _get_base_config_defaults(base_config: dict):
    template: Dict[str, Any] = base_config.get("variables", {}).get("properties", {})
    defaults = dict()
    for variable_name, attrs in template.items():
        if "default" in attrs:
            defaults[variable_name] = attrs["default"]

    return defaults


async def _resolve_default_references(variables: dict, session: AsyncSession) -> dict:
    """
    Iterate through discovered job_variables and resolve references to blocks. The input
    variables should have a format of:

    {
        "variable_name": {
            "$ref": {
                "block_document_id": "block_document_id"
            },
        "other_variable_name": "plain_value"
    }

    """
    for name, default_value in variables.items():
        if not isinstance(default_value, dict):
            continue

        if "$ref" not in default_value:
            continue

        reference_data = default_value.get("$ref")

        if (block_doc_id := reference_data.get("block_document_id")) is None:
            continue

        block_document = await models.block_documents.read_block_document_by_id(
            session, block_doc_id
        )
        if not block_document:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Block not found.")

        variables[name] = block_document.data

    return variables


async def validate_job_variables_for_flow_run(
    flow_run: Union[
        schemas.actions.DeploymentFlowRunCreate, schemas.actions.FlowRunUpdate
    ],
    deployment: schemas.core.Deployment,
    session: AsyncSession,
) -> None:
    """
    This will raise HTTP 404 error if the referenced block document or
    the actor does not have permissions to access that block. Therefore, this is only safe
    to use within the context of an API request
    """
    if deployment.work_queue is None or deployment.work_queue.work_pool is None:
        # if we aren't able to access a deployment's work pool, we don't have a
        # base job template to validate job variables against
        return

    variables_schema = deployment.work_queue.work_pool.base_job_template.get(
        "variables"
    )
    if not variables_schema:
        # There is no schema to validate.
        return

    base_vars = _get_base_config_defaults(
        deployment.work_queue.work_pool.base_job_template
    )
    base_vars = await _resolve_default_references(base_vars, session)
    flow_run_vars = flow_run.job_variables or {}
    job_vars = {**base_vars, **deployment.job_variables, **flow_run_vars}
    variables_schema = deployment.work_queue.work_pool.base_job_template.get(
        "variables"
    )

    try:
        validate(
            job_vars,
            variables_schema,
            raise_on_error=True,
            preprocess=True,
        )
    except ValidationError as exc:
        if isinstance(flow_run, schemas.actions.FlowRunUpdate):
            error_msg = f"Error updating flow run: {exc}"
        else:
            error_msg = f"Error creating flow run: {exc}"
        raise HTTPException(status.HTTP_409_CONFLICT, detail=error_msg)
