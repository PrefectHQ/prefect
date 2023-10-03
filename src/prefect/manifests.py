"""
Manifests are portable descriptions of one or more workflows within a given directory structure.

They are the foundational building blocks for defining Flow Deployments.
"""


from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field
else:
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
