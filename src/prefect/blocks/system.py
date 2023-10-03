from typing import Any

import pendulum

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, SecretStr
else:
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

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/4fcef2294b6eeb423b1332d1ece5156bf296ff96-48x48.png"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/system/#prefect.blocks.system.JSON"

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

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/c262ea2c80a2c043564e8763f3370c3db5a6b3e6-48x48.png"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/system/#prefect.blocks.system.String"

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
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/8b3da9a6621e92108b8e6a75b82e15374e170ff7-48x48.png"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/system/#prefect.blocks.system.DateTime"

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

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/c6f20e556dd16effda9df16551feecfb5822092b-48x48.png"
    _documentation_url = "https://docs.prefect.io/api-ref/prefect/blocks/system/#prefect.blocks.system.Secret"

    value: SecretStr = Field(
        default=..., description="A string value that should be kept secret."
    )

    def get(self):
        return self.value.get_secret_value()
