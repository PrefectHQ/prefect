import os

from pydantic.version import VERSION as PYDANTIC_VERSION

HAS_PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

USE_PYDANTIC_V2 = os.environ.get(
    "PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS", False
)
