import logging.handlers
import traceback
from types import TracebackType
from typing import Optional, Tuple, Type, Union

import orjson

from prefect.serializers import JSONSerializer

ExceptionInfoType = Union[
    Tuple[Type[BaseException], BaseException, Optional[TracebackType]],
    Tuple[None, None, None],
]


def format_exception_info(exc_info: ExceptionInfoType) -> dict:
    # if sys.exc_info() returned a (None, None, None) tuple,
    # then there's nothing to format
    if exc_info[0] is None:
        return {}

    (exception_type, exception_obj, exception_traceback) = exc_info
    return {
        "type": exception_type.__name__,
        "message": str(exception_obj),
        "traceback": "".join(traceback.format_tb(exception_traceback))
        if exception_traceback
        else None,
    }


class JsonFormatter(logging.Formatter):
    """
    Formats log records as a JSON string.

    The format may be specified as "pretty" to format the JSON with indents and
    newlines.
    """

    def __init__(self, fmt, dmft, style) -> None:  # noqa
        super().__init__()

        if fmt not in ["pretty", "default"]:
            raise ValueError("Format must be either 'pretty' or 'default'.")

        self.serializer = JSONSerializer(
            jsonlib="orjson",
            object_encoder="pydantic.json.pydantic_encoder",
            dumps_kwargs={"option": orjson.OPT_INDENT_2} if fmt == "pretty" else {},
        )

    def format(self, record: logging.LogRecord) -> str:
        record_dict = record.__dict__.copy()

        # replace any exception tuples returned by `sys.exc_info()`
        # with a JSON-serializable `dict`.
        if record.exc_info:
            record_dict["exc_info"] = format_exception_info(record.exc_info)

        log_json_bytes = self.serializer.dumps(record_dict)

        # JSONSerializer returns bytes; decode to string to conform to
        # the `logging.Formatter.format` interface
        return log_json_bytes.decode()
