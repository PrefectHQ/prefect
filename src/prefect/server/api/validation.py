from typing import Union

from prefect._vendor.fastapi import HTTPException, status

import prefect.server.schemas as schemas
from prefect.utilities.validation import validate_values_conform_to_schema


def _get_base_config_defaults(base_config: dict):
    template: dict = base_config.get("variables", {}).get("properties", {})
    defaults = dict()
    for variable_name, attrs in template.items():
        if "default" in attrs:
            defaults[variable_name] = attrs["default"]

    return defaults


def validate_job_variables_for_flow_run(
    flow_run: Union[
        schemas.actions.DeploymentFlowRunCreate, schemas.actions.FlowRunUpdate
    ],
    deployment: schemas.core.Deployment,
) -> None:
    base_vars = _get_base_config_defaults(
        deployment.work_queue.work_pool.base_job_template
    )
    flow_run_vars = flow_run.job_variables or {}
    job_vars = {**base_vars, **deployment.infra_overrides, **flow_run_vars}

    try:
        validate_values_conform_to_schema(
            job_vars,
            deployment.work_queue.work_pool.base_job_template.get("variables"),
        )
    except ValueError as exc:
        if isinstance(flow_run, schemas.actions.FlowRunUpdate):
            error_msg = f"Error updating flow run: {exc}"
        else:
            error_msg = f"Error creating flow run: {exc}"
        raise HTTPException(status.HTTP_409_CONFLICT, detail=error_msg)
