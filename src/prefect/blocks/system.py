from typing import Any

import pendulum
from pydantic import Field, SecretStr

from prefect.blocks.core import Block


class JSON(Block):
    """
    A block that represents JSON

    Attributes:
        value: A JSON-compatible value.

    Example:
        Load a stored JSON value:
        ```python
        from prefect.blocks.system import JSON

        json_block = JSON.load("BLOCK_NAME")
        ```
    """

    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/19W3Di10hhb4oma2Qer0x6/764d1e7b4b9974cd268c775a488b9d26/image16.png?h=250"

    value: Any = Field(default=..., description="A JSON-compatible value.")


class String(Block):
    """
    A block that represents a string

    Attributes:
        value: A string value.

    Example:
        Load a stored string value:
        ```python
        from prefect.blocks.system import String

        string_block = String.load("BLOCK_NAME")
        ```
    """

    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/4zjrZmh9tBrFiikeB44G4O/2ce1dbbac1c8e356f7c429e0f8bbb58d/image10.png?h=250"

    value: str = Field(default=..., description="A string value.")


class DateTime(Block):
    """
    A block that represents a datetime

    Attributes:
        value: An ISO 8601-compatible datetime value.

    Example:
        Load a stored JSON value:
        ```python
        from prefect.blocks.system import DateTime

        data_time_block = DateTime.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Date Time"
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/1gmljt5UBcAwEXHPnIofcE/0f3cf1da45b8b2df846e142ab52b1778/image21.png?h=250"

    value: pendulum.DateTime = Field(
        default=...,
        description="An ISO 8601-compatible datetime value.",
    )


class Secret(Block):
    """
    A block that represents a secret value. The value stored in this block will be obfuscated when
    this block is logged or shown in the UI.

    Attributes:
        value: A string value that should be kept secret.

    Example:
        ```python
        from prefect.blocks.system import Secret

        secret_block = Secret.load("BLOCK_NAME")

        # Access the stored secret
        secret_block.get()
        ```
    """

    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/5uUmyGBjRejYuGTWbTxz6E/3003e1829293718b3a5d2e909643a331/image8.png?h=250"

    value: SecretStr = Field(
        default=..., description="A string value that should be kept secret."
    )

    def get(self):
        return self.value.get_secret_value()
