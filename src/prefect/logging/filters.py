import logging
from collections.abc import Mapping
from typing import Any

from prefect.utilities.names import obfuscate


class _RedactedString(str):
    """
    A `str` subclass that stores a separate `repr` value.

    This allows logging's `%r` and `%a` conversions to use a redacted
    representation while `%s` and JSON serialization use the redacted
    `str` value.
    """

    __slots__ = ("_repr",)

    def __new__(cls, str_value: str, repr_value: str) -> "_RedactedString":
        instance = super().__new__(cls, str_value)
        instance._repr = repr_value
        return instance

    def __repr__(self) -> str:
        return self._repr

    def __reduce__(self) -> tuple[type, tuple[str, str]]:
        return (type(self), (str(self), self._repr))


def redact_substr(obj: Any, substr: str) -> Any:
    """
    Redact a string from a potentially nested object.

    Standard collections (list, tuple, set, dict, and other `Mapping`
    instances) are traversed recursively and have their string values redacted
    while preserving shape. Non-container objects are redacted by replacing
    their `str` and `repr` values with obfuscated versions, avoiding the
    need to reconstruct arbitrary user objects (e.g. dataclasses with
    `init=False` fields or Pydantic models).

    Args:
        obj: The object to redact the string from
        substr: The string to redact.

    Returns:
        Any: The object with the API key redacted.
    """
    if isinstance(obj, str):
        return obj.replace(substr, obfuscate(substr))

    if isinstance(obj, (list, tuple, set)):
        seq = obj
        items = [redact_substr(item, substr) for item in seq]
        if all(item is orig for item, orig in zip(items, seq)):
            return obj
        # Preserve namedtuple types.
        if hasattr(type(seq), "_make"):
            return type(seq)._make(items)
        return type(seq)(items)

    if isinstance(obj, Mapping):
        mapping = obj
        items = [
            (redact_substr(key, substr), redact_substr(value, substr))
            for key, value in mapping.items()
        ]
        if all(
            k1 is k2 and v1 is v2 for (k1, v1), (k2, v2) in zip(items, mapping.items())
        ):
            return obj
        # Return a plain dict so that arbitrary Mapping types (e.g. ChainMap)
        # can still be formatted by logging's `%` operator and serialized as
        # JSON without reconstructing the original mapping type.
        return dict(items)

    # For opaque objects, redact their rendered string representations.  This
    # handles exceptions, dataclasses, Pydantic models, and other lazy logging
    # arguments whose `__str__` or `__repr__` may contain the secret.
    str_value = str(obj)
    repr_value = repr(obj)
    redacted_str = str_value.replace(substr, obfuscate(substr))
    redacted_repr = repr_value.replace(substr, obfuscate(substr))
    if redacted_str is not str_value or redacted_repr is not repr_value:
        return _RedactedString(redacted_str, redacted_repr)

    return obj


class ObfuscateApiKeyFilter(logging.Filter):
    """
    A logging filter that obfuscates any string that matches the obfuscate_string function.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Need to import here to avoid circular imports
        from prefect.settings import PREFECT_API_KEY

        api_key = PREFECT_API_KEY.value()
        if api_key:
            record.msg = redact_substr(record.msg, api_key)
            if record.args is not None:
                record.args = redact_substr(record.args, api_key)

        return True
