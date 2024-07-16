from copy import deepcopy
from typing import Any, Dict, List, Optional
from uuid import UUID

import jsonschema
from pydantic import Field, field_validator, model_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    remove_old_deployment_fields,
    return_none_schedule,
)
from prefect.client.schemas.schedules import SCHEDULE_TYPES


class DeploymentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a deployment."""

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values):
        return remove_old_deployment_fields(values)

    @field_validator("schedule")
    @classmethod
    def validate_none_schedule(cls, v):
        return return_none_schedule(v)

    version: Optional[str] = Field(None)
    schedule: Optional[SCHEDULE_TYPES] = Field(None)
    description: Optional[str] = Field(None)
    is_schedule_active: bool = Field(None)
    parameters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(default_factory=list)
    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    path: Optional[str] = Field(None)
    job_variables: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
    )
    entrypoint: Optional[str] = Field(None)
    storage_document_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )

    def check_valid_configuration(self, base_job_template: dict):
        """Check that the combination of base_job_template defaults
        and job_variables conforms to the specified schema.
        """
        variables_schema = deepcopy(base_job_template.get("variables"))

        if variables_schema is not None:
            # jsonschema considers required fields, even if that field has a default,
            # to still be required. To get around this we remove the fields from
            # required if there is a default present.
            required = variables_schema.get("required")
            properties = variables_schema.get("properties")
            if required is not None and properties is not None:
                for k, v in properties.items():
                    if "default" in v and k in required:
                        required.remove(k)

        if variables_schema is not None:
            jsonschema.validate(self.job_variables, variables_schema)