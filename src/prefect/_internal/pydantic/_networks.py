from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_PYDANTIC_V2

if HAS_PYDANTIC_V2 and USE_PYDANTIC_V2:
    from pydantic.networks import HttpUrl
elif HAS_PYDANTIC_V2:
    from pydantic.v1.networks import HttpUrl
else:
    from pydantic.networks import HttpUrl

__all__ = ["HttpUrl"]
