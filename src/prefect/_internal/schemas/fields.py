import datetime
from typing import Optional
from uuid import UUID

import pendulum
from typing_extensions import TypeAlias

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import BaseModel, Field
else:
    from pydantic import BaseModel, Field


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


class CreatedBy(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the creator of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the creator of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the creator."
    )


class UpdatedBy(BaseModel):
    id: Optional[UUID] = Field(
        default=None, description="The id of the updater of the object."
    )
    type: Optional[str] = Field(
        default=None, description="The type of the updater of the object."
    )
    display_value: Optional[str] = Field(
        default=None, description="The display value for the updater."
    )
