### A convenience module to allow for easy switching between pydantic versions.

### Note this introduces a marginally worse import time, since
### the import of any one of these symbols will import all of them.

### This is a tradeoff we're willing to make for now until pydantic v1 is
### no longer supported.

from pydantic.version import VERSION as PYDANTIC_VERSION

HAS_PYDANTIC_V2 = PYDANTIC_VERSION.startswith("2.")
