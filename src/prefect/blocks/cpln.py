import os

from prefect._internal.pydantic import HAS_PYDANTIC_V2
from prefect.blocks.core import Block

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field


class CplnConfig(Block):
    """
    Stores configuration for interacting with the Control Plane platform.

    Attributes:
        token: The Control Plane Service Account token of a specific organization to use.

    Example:
        Load a saved Control Plane config:
        ```python
        from prefect.blocks.cpln import CplnConfig

        config_block = CplnConfig.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Cpln Config"
    _logo_url = "https://console.cpln.io/resources/logos/controlPlaneLogoOnly.svg"
    _documentation_url = "https://docs.controlplane.com"

    token: str = Field(
        default_factory=lambda: os.getenv("CPLN_TOKEN"),
        description="The Control Plane Service Account token of a specific organization. Defaults to the value specified in the environment variable CPLN_TOKEN.",
    )
