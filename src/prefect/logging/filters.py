import logging
from typing import Any

from prefect.utilities.collections import visit_collection
from prefect.utilities.names import obfuscate


def redact_substr(obj: Any, substr: str):
    """
    Redact a string from a potentially nested object.

    Args:
        obj: The object to redact the string from
        substr: The string to redact.

    Returns:
        Any: The object with the API key redacted.
    """

    def redact_item(item):
        if isinstance(item, str):
            return item.replace(substr, obfuscate(substr))
        return item

    redacted_obj = visit_collection(obj, visit_fn=redact_item, return_data=True)
    return redacted_obj


class ObfuscateApiKeyFilter(logging.Filter):
    """
    A logging filter that obfuscates any string that matches the obfuscate_string function.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Need to import here to avoid circular imports
        from prefect.settings import PREFECT_API_KEY

        if PREFECT_API_KEY:
            record.msg = redact_substr(record.msg, PREFECT_API_KEY.value())

        return True
