import logging
from typing import Any, Optional

from pythonjsonlogger.core import RESERVED_ATTRS
from pythonjsonlogger.json import JsonFormatter

DEFAULT_JSON_REFKEY = "object"


class KopfObjectJsonFormatter(JsonFormatter):
    """
    Log formatter for kopf objects.

    This formatter will filter unserializable fields from the log record,
    which the `prefect` JSON formatter is unable to do.
    """

    def __init__(
        self,
        *args: Any,
        refkey: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        # Avoid type checking, as the args are not in the parent constructor.
        reserved_attrs = kwargs.pop("reserved_attrs", RESERVED_ATTRS)
        reserved_attrs = set(reserved_attrs)
        reserved_attrs |= {"k8s_skip", "k8s_ref", "settings"}
        kwargs |= dict(reserved_attrs=reserved_attrs)
        kwargs.setdefault("timestamp", True)
        super().__init__(*args, **kwargs)
        self._refkey: str = refkey or DEFAULT_JSON_REFKEY

    def add_fields(
        self,
        log_record: dict[str, object],
        record: logging.LogRecord,
        message_dict: dict[str, object],
    ) -> None:
        super().add_fields(log_record, record, message_dict)

        if self._refkey and hasattr(record, "k8s_ref"):
            ref = getattr(record, "k8s_ref")
            log_record[self._refkey] = ref

        if "severity" not in log_record:
            log_record["severity"] = (
                "debug"
                if record.levelno <= logging.DEBUG
                else "info"
                if record.levelno <= logging.INFO
                else "warn"
                if record.levelno <= logging.WARNING
                else "error"
                if record.levelno <= logging.ERROR
                else "fatal"
            )
