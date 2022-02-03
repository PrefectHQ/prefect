import logging
import logging.config
import logging.handlers
from pprint import pformat

from fastapi.encoders import jsonable_encoder


def safe_jsonable(obj):
    try:
        return jsonable_encoder(obj)
    except:
        return "<unserializable>"


class JsonFormatter(logging.Formatter):
    """
    Formats log records as a JSON string.

    If a log record attribute is not JSON serialiazable, it will be dropped from the
    output.

    The format may be specified as "pretty" to format the JSON with indents and
    newlines.
    """

    def __init__(self, fmt, dmft, style) -> None:
        if fmt not in ["pretty", "default"]:
            raise ValueError("Format must be either 'pretty' or 'default'.")
        self.fmt = fmt

    def format(self, record: logging.LogRecord):
        format_fn = pformat if self.fmt == "pretty" else str
        return format_fn(
            {key: safe_jsonable(val) for key, val in record.__dict__.items()}
        )
