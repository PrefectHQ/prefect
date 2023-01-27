"""
Manifests are portable descriptions of one or more workflows within a given directory structure.

They are the foundational building blocks for defining Flow Deployments.
"""


from pydantic import BaseModel, Field

from prefect.utilities.callables import ParameterSchema


class Manifest(BaseModel):
    """A JSON representation of a flow."""

    flow_name: str = Field(default=..., description="The name of the flow.")
    import_path: str = Field(
        default=..., description="The relative import path for the flow."
    )
    parameter_openapi_schema: ParameterSchema = Field(
        default=..., description="The OpenAPI schema of the flow's parameters."
    )
