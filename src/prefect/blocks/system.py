from typing import Any

import pendulum

from prefect.blocks.core import Block, register_block


@register_block
class JSON(Block):
    """
    A block that represents JSON
    """

    # any JSON-compatible value
    value: Any


@register_block
class String(Block):
    """
    A block that represents a string
    """

    value: str


@register_block
class DateTime(Block):
    """
    A block that represents a datetime
    """

    # any JSON-compatible value
    value: pendulum.DateTime
