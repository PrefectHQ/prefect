import typing

from prefect._internal.pydantic._flags import (
    HAS_PYDANTIC_V2,
    USE_PYDANTIC_V2,
)

if typing.TYPE_CHECKING:
    from pydantic import (
        BaseModel,
        ConfigDict,
        Field,
        PrivateAttr,
        SecretStr,
        ValidationError,
    )
    from pydantic.fields import FieldInfo

if HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
    from pydantic.v1 import (
        BaseModel,
        ConfigDict,
        Field,
        PrivateAttr,
        SecretStr,
        ValidationError,
    )
    from pydantic.v1.fields import FieldInfo
else:
    from pydantic import (
        BaseModel,
        ConfigDict,
        Field,
        PrivateAttr,
        SecretStr,
        ValidationError,
    )
    from pydantic.fields import FieldInfo

__all__ = [
    "BaseModel",
    "Field",
    "FieldInfo",
    "PrivateAttr",
    "SecretStr",
    "ConfigDict",
    "ValidationError",
]
