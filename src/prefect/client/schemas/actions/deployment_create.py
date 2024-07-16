from copy import deepcopy
from typing import Any, Dict, List, Optional
from uuid import UUID

import jsonschema
from pydantic import Field, field_validator, model_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    convert_to_strings,
    remove_old_deployment_fields,
)
from prefect.client.schemas.schedules import SCHEDULE_TYPES

from .deployment_schedule_create import DeploymentScheduleCreate


class DeploymentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a deployment."""

    @model_validator(mode="before")
    @classmethod
    def remove_old_fields(cls, values):
        return remove_old_deployment_fields(values)

    @field_validator("description", "tags", mode="before")
    @classmethod
    def convert_to_strings(cls, values):
        return convert_to_strings(values)

    name: str = Field(..., description="The name of the deployment.")
    flow_id: UUID = Field(..., description="The ID of the flow to deploy.")
    is_schedule_active: Optional[bool] = Field(None)
    paused: Optional[bool] = Field(None)
    schedules: List[DeploymentScheduleCreate] = Field(
        default_factory=list,
        description="A list of schedules for the deployment.",
    )
    enforce_parameter_schema: Optional[bool] = Field(
        default=None,
        description=(
            "Whether or not the deployment should enforce the parameter schema."
        ),
    )
    parameter_openapi_schema: Optional[Dict[str, Any]] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for flow runs scheduled by the deployment.",
    )
    tags: List[str] = Field(default_factory=list)
    pull_steps: Optional[List[dict]] = Field(None)

    work_queue_name: Optional[str] = Field(None)
    work_pool_name: Optional[str] = Field(
        default=None,
        description="The name of the deployment's work pool.",
        examples=["my-work-pool"],
    )
    storage_document_id: Optional[UUID] = Field(None)
    infrastructure_document_id: Optional[UUID] = Field(None)
    schedule: Optional[SCHEDULE_TYPES] = Field(None)
    description: Optional[str] = Field(None)
    path: Optional[str] = Field(None)
    version: Optional[str] = Field(None)
    entrypoint: Optional[str] = Field(None)
    job_variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Overrides to apply to flow run infrastructure at runtime.",
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

            jsonschema.validate(self.job_variables, variables_schema)