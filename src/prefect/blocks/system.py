from __future__ import annotations

import json
from typing import Annotated, Generic, TypeVar, Union

from pydantic import (
    Field,
    HttpUrl,
    JsonValue,
    SecretStr,
    StrictStr,
    field_validator,
)
from pydantic import Secret as PydanticSecret

from prefect.blocks.core import Block

_SecretValueType = Union[
    Annotated[StrictStr, Field(title="string")],
    Annotated[JsonValue, Field(title="JSON")],
]

T = TypeVar("T", bound=_SecretValueType)


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
