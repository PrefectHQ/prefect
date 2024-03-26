import typing

from prefect._internal.pydantic._flags import (
    HAS_PYDANTIC_V2,
    USE_PYDANTIC_V2,
)

if typing.TYPE_CHECKING:
    from pydantic import BaseModel

if HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
    from pydantic.v1 import BaseModel
else:
    from pydantic import BaseModel

__all__ = ["BaseModel"]
