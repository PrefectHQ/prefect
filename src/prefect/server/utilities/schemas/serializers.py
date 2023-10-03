from typing import Any, TypeVar

import orjson

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel
else:
    from pydantic import BaseModel


T = TypeVar("T")
B = TypeVar("B", bound=BaseModel)


def orjson_dumps(v: Any, *, default: Any) -> str:
    """
    Utility for dumping a value to JSON using orjson.

    orjson.dumps returns bytes, to match standard json.dumps we need to decode.
    """
    return orjson.dumps(v, default=default).decode()


def orjson_dumps_extra_compatible(v: Any, *, default: Any) -> str:
    """
    Utility for dumping a value to JSON using orjson, but allows for
    1) non-string keys: this is helpful for situations like pandas dataframes,
    which can result in non-string keys
    2) numpy types: for serializing numpy arrays

    orjson.dumps returns bytes, to match standard json.dumps we need to decode.
    """
    return orjson.dumps(
        v, default=default, option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
    ).decode()
