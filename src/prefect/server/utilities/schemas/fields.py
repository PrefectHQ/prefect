import datetime

import pendulum
from typing_extensions import TypeAlias

# Rather than subclassing pendulum.DateTime to add our pydantic-specific validation,
# which will lead to a lot of funky typing issues, we'll just monkeypatch the pydantic
# validators onto the class.  Retaining this type alias means that we can still use it
# as we have been in class definitions, also guaranteeing that we'll be applying these
# validators by importing this module.

DateTimeTZ: TypeAlias = pendulum.DateTime


def _datetime_patched_classmethod(function):
    if hasattr(DateTimeTZ, function.__name__):
        return function
    setattr(DateTimeTZ, function.__name__, classmethod(function))
    return function


@_datetime_patched_classmethod
def __get_validators__(cls):
    yield getattr(cls, "validate")


@_datetime_patched_classmethod
def validate(cls, v) -> pendulum.DateTime:
    if isinstance(v, str):
        parsed = pendulum.parse(v)
        assert isinstance(parsed, pendulum.DateTime)
        return parsed
    elif isinstance(v, datetime.datetime):
        return pendulum.instance(v)
    else:
        raise ValueError("Unrecognized datetime.")
