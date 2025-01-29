from __future__ import annotations

import json
from typing import Annotated, Any, Generic, TypeVar, Union

from pydantic import (
    Field,
    HttpUrl,
    JsonValue,
    SecretStr,
    StrictStr,
    field_validator,
)
from pydantic import Secret as PydanticSecret

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect.blocks.core import Block
from prefect.types import DateTime as PydanticDateTime

_SecretValueType = Union[
    Annotated[StrictStr, Field(title="string")],
    Annotated[JsonValue, Field(title="JSON")],
]

T = TypeVar("T", bound=_SecretValueType)


@deprecated_class(
    start_date="Jun 2024",
    end_date="Jun 2025",
    help="Use Variables to store json data instead.",
)
class JSON(Block):
    """
    A block that represents JSON. Deprecated, please use Variables to store JSON data instead.

    Attributes:
        value: A JSON-compatible value.

    Example:
        Load a stored JSON value:
        ```python
        from prefect.blocks.system import JSON

        json_block = JSON.load("BLOCK_NAME")
        ```
    """

    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/4fcef2294b6eeb423b1332d1ece5156bf296ff96-48x48.png"
    )
    _documentation_url = HttpUrl("https://docs.prefect.io/latest/develop/blocks")

    value: Any = Field(default=..., description="A JSON-compatible value.")


@deprecated_class(
    start_date="Jun 2024",
    end_date="Jun 2025",
    help="Use Variables to store string data instead.",
)
class String(Block):
    """
    A block that represents a string. Deprecated, please use Variables to store string data instead.

    Attributes:
        value: A string value.

    Example:
        Load a stored string value:
        ```python
        from prefect.blocks.system import String

        string_block = String.load("BLOCK_NAME")
        ```
    """

    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/c262ea2c80a2c043564e8763f3370c3db5a6b3e6-48x48.png"
    )
    _documentation_url = HttpUrl("https://docs.prefect.io/latest/develop/blocks")

    value: str = Field(default=..., description="A string value.")


@deprecated_class(
    start_date="Jun 2024",
    end_date="Jun 2025",
    help="Use Variables to store datetime data instead.",
)
class DateTime(Block):
    """
    A block that represents a datetime. Deprecated, please use Variables to store datetime data instead.

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
    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/8b3da9a6621e92108b8e6a75b82e15374e170ff7-48x48.png"
    )
    _documentation_url = HttpUrl("https://docs.prefect.io/latest/develop/blocks")

    value: PydanticDateTime = Field(
        default=...,
        description="An ISO 8601-compatible datetime value.",
    )


class Secret(Block, Generic[T]):
    """
    A block that represents a secret value. The value stored in this block will be obfuscated when
    this block is viewed or edited in the UI.

    Attributes:
        value: A value that should be kept secret.

    Example:
        ```python
        from prefect.blocks.system import Secret

        Secret(value="sk-1234567890").save("BLOCK_NAME", overwrite=True)

        secret_block = Secret.load("BLOCK_NAME")

        # Access the stored secret
        secret_block.get()
        ```
    """

    _logo_url = HttpUrl(
        "https://cdn.sanity.io/images/3ugk85nk/production/c6f20e556dd16effda9df16551feecfb5822092b-48x48.png"
    )
    _documentation_url = HttpUrl("https://docs.prefect.io/latest/develop/blocks")
    _description = "A block that represents a secret value. The value stored in this block will be obfuscated when this block is viewed or edited in the UI."

    value: Union[SecretStr, PydanticSecret[T]] = Field(
        default=...,
        description="A value that should be kept secret.",
        examples=["sk-1234567890", {"username": "johndoe", "password": "s3cr3t"}],
        json_schema_extra={
            "writeOnly": True,
            "format": "password",
        },
    )

    @field_validator("value", mode="before")
    def validate_value(
        cls, value: Union[T, SecretStr, PydanticSecret[T]]
    ) -> Union[SecretStr, PydanticSecret[T]]:
        if isinstance(value, (PydanticSecret, SecretStr)):
            return value
        else:
            return PydanticSecret[type(value)](value)

    def get(self) -> T | str:
        value = self.value.get_secret_value()
        try:
            if isinstance(value, (str)):
                return json.loads(value)
            return value
        except (TypeError, json.JSONDecodeError):
            return value
