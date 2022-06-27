import os
from typing import Any

import pendulum
from pydantic import Field

from prefect.blocks.core import Block
from prefect.utilities.dispatch import register_type


@register_type
class JSON(Block):
    """
    A block that represents JSON
    """

    value: Any = Field(..., description="A JSON-compatible value")


@register_type
class String(Block):
    """
    A block that represents a string
    """

    value: str = Field(..., description="A string value.")


@register_type
class DateTime(Block):
    """
    A block that represents a datetime
    """

    value: pendulum.DateTime = Field(
        ...,
        description="An ISO 8601-compatible datetime value.",
    )


@register_block
class EnvironmentVariable(Block):
    """
    A block that pulls its value from an environment variable.

    The variable it uses is configurable and can be set in the Prefect UI; the
    block will recover its value at runtime from that variable. This allows
    behavior to be modified remotely by changing the environment variable name.

    Example:
    ```python
    block = EnvironmentVariable(name="MY_ENV_VAR")

    # loads the value of MY_ENV_VAR
    block.get()
    ```

    """

    name: str = Field(
        ...,
        description="The name of an environment variable that holds the value for this block",
    )

    def get(self):
        return os.getenv(self.name)
