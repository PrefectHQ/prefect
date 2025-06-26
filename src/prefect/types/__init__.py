from __future__ import annotations

from functools import partial
from typing import Annotated, Any, Optional, TypeVar, Union
from typing_extensions import Literal
import orjson
import pydantic

from ._datetime import DateTime, Date
from .names import (
    Name,
    NameOrEmpty,
    NonEmptyishName,
    BANNED_CHARACTERS,
    WITHOUT_BANNED_CHARACTERS,
    MAX_VARIABLE_NAME_LENGTH,
    URILike,
    ValidAssetKey,
)
from pydantic import (
    BeforeValidator,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    TypeAdapter,
)
from zoneinfo import available_timezones

T = TypeVar("T")

MAX_VARIABLE_VALUE_LENGTH = 5000

NonNegativeInteger = Annotated[int, Field(ge=0)]
PositiveInteger = Annotated[int, Field(gt=0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]

TimeZone = Annotated[
    str,
    Field(
        default="UTC",
        pattern="|".join(
            [z for z in sorted(available_timezones()) if "localtime" not in z]
        ),
    ),
]


VariableValue = Union[
    StrictStr,
    StrictInt,
    StrictBool,
    StrictFloat,
    None,
    dict[str, Any],
    list[Any],
]


def check_variable_value(value: object) -> object:
    try:
        json_string = orjson.dumps(value)
    except orjson.JSONEncodeError:
        raise ValueError("Variable value must be serializable to JSON")

    if value is not None and len(json_string) > MAX_VARIABLE_VALUE_LENGTH:
        raise ValueError(
            f"Variable value must be less than {MAX_VARIABLE_VALUE_LENGTH} characters"
        )
    return value


StrictVariableValue = Annotated[VariableValue, BeforeValidator(check_variable_value)]

LaxUrl = Annotated[str, BeforeValidator(lambda x: str(x).strip())]

StatusCode = Annotated[int, Field(ge=100, le=599)]


def cast_none_to_empty_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    return value


KeyValueLabels = Annotated[
    dict[str, Union[StrictBool, StrictInt, StrictFloat, str]],
    BeforeValidator(cast_none_to_empty_dict),
]


ListOfNonEmptyStrings = Annotated[
    list[str],
    BeforeValidator(lambda x: [str(s) for s in x if str(s).strip()]),
]


class SecretDict(pydantic.Secret[dict[str, Any]]):
    pass


def validate_set_T_from_delim_string(
    value: Union[str, T, set[T], None], type_: Any, delim: str | None = None
) -> set[T]:
    """
    "no-info" before validator useful in scooping env vars

    e.g. `PREFECT_CLIENT_RETRY_EXTRA_CODES=429,502,503` -> `{429, 502, 503}`
    e.g. `PREFECT_CLIENT_RETRY_EXTRA_CODES=429` -> `{429}`
    """
    if not value:
        return set()

    T_adapter = TypeAdapter(type_)
    delim = delim or ","
    if isinstance(value, str):
        return {T_adapter.validate_strings(s.strip()) for s in value.split(delim)}
    errors: list[pydantic.ValidationError] = []
    try:
        return {T_adapter.validate_python(value)}
    except pydantic.ValidationError as e:
        errors.append(e)
    try:
        return TypeAdapter(set[type_]).validate_python(value)
    except pydantic.ValidationError as e:
        errors.append(e)
    raise ValueError(f"Invalid set[{type_}]: {errors}")


ClientRetryExtraCodes = Annotated[
    Union[str, StatusCode, set[StatusCode], None],
    BeforeValidator(partial(validate_set_T_from_delim_string, type_=StatusCode)),
]


def parse_retry_delay_input(value: Any) -> Any:
    """
    Parses various inputs (string, int, float, list) into a format suitable
    for TaskRetryDelaySeconds (int, float, list[float], or None).
    Handles comma-separated strings for lists of delays.
    """
    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            return None  # Treat empty or whitespace-only string as None

        delim = ","
        # Split and filter empty strings that result from multiple commas (e.g., "10,,20")
        parts = [s.strip() for s in stripped_value.split(delim) if s.strip()]

        if not parts:  # e.g., value was just "," or " , "
            return None

        def _parse_num_part(part_str: str) -> Union[float, int]:
            try:
                # Prefer float to align with list[float] in TaskRetryDelaySeconds
                return TypeAdapter(float).validate_strings(part_str)
            except pydantic.ValidationError:
                try:
                    return TypeAdapter(int).validate_strings(part_str)
                except pydantic.ValidationError as e_int:
                    raise ValueError(
                        f"Invalid number format '{part_str}' for retry delay."
                    ) from e_int

        if len(parts) == 1:
            return _parse_num_part(parts[0])
        else:
            return [_parse_num_part(p) for p in parts]

    # For non-string inputs (int, float, list, None, etc.), pass them through.
    # Pydantic will then validate them against Union[int, float, list[float], None].
    return value


TaskRetryDelaySeconds = Annotated[
    Union[str, int, float, list[float], None],
    BeforeValidator(parse_retry_delay_input),
]

LogLevel = Annotated[
    Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    BeforeValidator(lambda x: x.upper()),
]


def convert_none_to_empty_dict(v: Optional[KeyValueLabels]) -> KeyValueLabels:
    return v or {}


KeyValueLabelsField = Annotated[
    KeyValueLabels,
    Field(
        default_factory=dict,
        description="A dictionary of key-value labels. Values can be strings, numbers, or booleans.",
        examples=[{"key": "value1", "key2": 42}],
    ),
    BeforeValidator(convert_none_to_empty_dict),
]


__all__ = [
    "BANNED_CHARACTERS",
    "WITHOUT_BANNED_CHARACTERS",
    "ClientRetryExtraCodes",
    "Date",
    "DateTime",
    "LogLevel",
    "KeyValueLabelsField",
    "MAX_VARIABLE_NAME_LENGTH",
    "MAX_VARIABLE_VALUE_LENGTH",
    "NonNegativeInteger",
    "PositiveInteger",
    "ListOfNonEmptyStrings",
    "NonNegativeFloat",
    "Name",
    "NameOrEmpty",
    "NonEmptyishName",
    "ValidAssetKey",
    "SecretDict",
    "StatusCode",
    "StrictVariableValue",
    "TaskRetryDelaySeconds",
    "URILike",
]
