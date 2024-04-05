from typing import TYPE_CHECKING

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

if TYPE_CHECKING:
    # BaseSettings is a subclass of pydantic BaseModel, so but isn't available as a top-level import
    # in pydantic v2, so for type-checking purposes we'll treat it as a BaseModel
    from pydantic import BaseModel as BaseSettings
elif HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    from pydantic_settings import BaseSettings
elif HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
    from pydantic.v1 import BaseSettings
else:
    from pydantic import BaseSettings

__all__ = ["BaseSettings"]
