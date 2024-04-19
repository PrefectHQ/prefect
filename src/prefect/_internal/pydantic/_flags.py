"""
This file defines flags that determine whether Pydantic V2 is available and whether its features should be used.
"""
import os

# Retrieve current version of Pydantic installed in environment
from pydantic.version import VERSION as PYDANTIC_VERSION

# Check if Pydantic version 2 is the installed version
HAS_PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")

# Determine if Pydantic v2 internals should be used based on an environment variable.
USE_PYDANTIC_V2 = os.environ.get(
    "PREFECT_EXPERIMENTAL_ENABLE_PYDANTIC_V2_INTERNALS", False
) in {"1", "true", "True"}

USE_V2_MODELS = HAS_PYDANTIC_V2 and USE_PYDANTIC_V2

# Set to True if Pydantic v2 is present but not enabled, indicating deprecation warnings may occur.
EXPECT_DEPRECATION_WARNINGS = HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2
