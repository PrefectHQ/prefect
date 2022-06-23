import os
from typing import Any

import pendulum
from pydantic import Field

from prefect.blocks.core import Block, register_block


@register_block
class JSON(Block):
    """
    A block that represents JSON
    """

    # any JSON-compatible value
    value: Any = Field(..., description="A JSON-compatible value")


@register_block
class String(Block):
    """
    A block that represents a string
    """

    value: str = Field(..., description="A string value.")


@register_block
class DateTime(Block):
    """
    A block that represents a datetime
    """

    value: pendulum.DateTime = Field(
        ...,
        description="An ISO 8601-compatible datetime value.",
    )


@register_block
class EnvVar(Block):
    """
    A block that pulls its value from an environment variable.

    The env var it uses is configurable and can be set in the Prefect UI; the
    block will recover its value only at runtime from the specified env var.

    Example:
    ```python
    block = EnvVar(env_var="MY_ENV_VAR")

    # loads the value of MY_ENV_VAR
    block.get()
    ```

    """

    env_var: str = Field(
        ...,
        description="The name of an environment variable that holds the value for this block",
    )

    def get(self):
        return os.getenv(self.env_var)
