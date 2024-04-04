from typing import TYPE_CHECKING
from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

if TYPE_CHECKING:
    from pydantic_settings import BaseSettings

if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    from pydantic_settings import BaseSettings
if HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
    from pydantic.v1 import BaseSettings
if not HAS_PYDANTIC_V2:
    from pydantic import BaseSettings

__all__ = ["BaseSettings"]
