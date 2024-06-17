import logging.handlers
import sys
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
        "traceback": (
            "".join(traceback.format_tb(exception_traceback))
            if exception_traceback
            else None
        ),
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
            dumps_kwargs={"option": orjson.OPT_INDENT_2} if fmt == "pretty" else {},
        )

    def format(self, record: logging.LogRecord) -> str:
        record_dict = record.__dict__.copy()

        # GCP severity detection compatibility
        record_dict.setdefault("severity", record.levelname)

        # replace any exception tuples returned by `sys.exc_info()`
        # with a JSON-serializable `dict`.
        if record.exc_info:
            record_dict["exc_info"] = format_exception_info(record.exc_info)

        log_json_bytes = self.serializer.dumps(record_dict)

        # JSONSerializer returns bytes; decode to string to conform to
        # the `logging.Formatter.format` interface
        return log_json_bytes.decode()


class PrefectFormatter(logging.Formatter):
    def __init__(
        self,
        format=None,
        datefmt=None,
        style="%",
        validate=True,
        *,
        defaults=None,
        task_run_fmt: Optional[str] = None,
        flow_run_fmt: Optional[str] = None,
    ) -> None:
        """
        Implementation of the standard Python formatter with support for multiple
        message formats.

        """
        # See https://github.com/python/cpython/blob/c8c6113398ee9a7867fe9b08bc539cceb61e2aaa/Lib/logging/__init__.py#L546
        # for implementation details

        init_kwargs = {}
        style_kwargs = {}

        # defaults added in 3.10
        if sys.version_info >= (3, 10):
            init_kwargs["defaults"] = defaults
            style_kwargs["defaults"] = defaults

        init_kwargs["validate"] = validate

        super().__init__(format, datefmt, style, **init_kwargs)

        self.flow_run_fmt = flow_run_fmt
        self.task_run_fmt = task_run_fmt

        # Retrieve the style class from the base class to avoid importing private
        # `_STYLES` mapping
        style_class = type(self._style)

        self._flow_run_style = (
            style_class(flow_run_fmt, **style_kwargs) if flow_run_fmt else self._style
        )
        self._task_run_style = (
            style_class(task_run_fmt, **style_kwargs) if task_run_fmt else self._style
        )
        if validate:
            self._flow_run_style.validate()
            self._task_run_style.validate()

    def formatMessage(self, record: logging.LogRecord):
        if record.name == "prefect.flow_runs":
            style = self._flow_run_style
        elif record.name == "prefect.task_runs":
            style = self._task_run_style
        else:
            style = self._style

        return style.format(record)
