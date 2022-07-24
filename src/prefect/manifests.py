"""
Manifests are portable descriptions of one or more workflows within a given directory structure.

They are the foundational building blocks for defining Flow Deployments.
"""

import json
from typing import List

from pydantic import BaseModel, Field, SecretBytes, SecretStr

from prefect.utilities.callables import ParameterSchema, parameter_schema


class Manifest(BaseModel):
    """A JSON representation of a flow."""

    flow_name: str = Field(..., description="The name of the flow.")
    import_path: str = Field(..., description="The relative import path for the flow.")
    initialize: List[str] = Field(
        None,
        description="A set of initialization commands to be called prior to running the flow.",
    )
    flow_parameter_schema: ParameterSchema = Field(
        ..., description="The parameter schema of the flow, including defaults."
    )
