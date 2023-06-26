import copy
from dataclasses import dataclass
from typing import Any, Optional, Type, TypeVar

from pydantic import BaseModel

B = TypeVar("B", bound=BaseModel)


@dataclass
class _FieldFrom:
    """Container for holding the origin of a field's definition"""

    origin: Type[BaseModel]


def FieldFrom(origin: Type[BaseModel]) -> Any:
    """
    Indicates that the given field is to be copied from another class by
    `copy_model_fields`.
    """
    return _FieldFrom(origin=origin)


def copy_model_fields(model_class: Type[B]) -> Type[B]:
    """
    A class decorator which copies field definitions and field validators from other
    Pydantic BaseModel classes.  This does _not_ make the model a subclass of any of
    the copied field's owning classes, nor does this copy root validators from any of
    those classes.  Note that you should still include the type hint for the field in
    order to make typing explicit.

    Use this decorator and the corresponding `FieldFrom` to compose response and
    action schemas from other classes.

    Examples:

        >>> from pydantic import BaseModel
        >>> from prefect.server.utilities.schemas import copy_model_fields, FieldFrom
        >>>
        >>> class Parent(BaseModel):
        ...     name: str
        ...     sensitive: str
        >>>
        >>> @copy_model_fields
        >>> class Derived(BaseModel):
        ...     name: str = FieldFrom(Parent)
        ...     my_own: str

        In this example, `Derived` will have the fields `name`, and `my_own`, with the
        `name` field being a complete copy of the `Parent.name` field.

    """
    for name, field in model_class.__fields__.items():
        if not isinstance(field.default, _FieldFrom):
            continue

        origin = field.default.origin

        origin_field = origin.__fields__[name]

        # For safety, types defined on the model must match those of the origin
        # We make an exception here for `Optional` where the model can make the same
        # type definition nullable.
        if (
            field.type_ != origin_field.type_
            and not field.type_ == Optional[origin_field.type_]
        ):
            if not issubclass(
                origin_field.type_,
                field.type_,
            ):
                raise TypeError(
                    f"Field {name} ({field.type_}) does not match the type of the"
                    f" origin field {origin_field.type_}"
                )

        # Create a copy of the origin field
        new_field = copy.deepcopy(origin_field)

        # Retain any validators from the model field
        new_field.post_validators = new_field.post_validators or []
        new_field.pre_validators = new_field.pre_validators or []
        new_field.post_validators.extend(field.post_validators or [])
        new_field.pre_validators.extend(field.pre_validators or [])

        # Retain "optional" from the model field
        new_field.required = field.required
        new_field.allow_none = field.allow_none

        model_class.__fields__[name] = new_field

        if name in origin.__validators__:
            # The type: ignores here are because pydantic has a mistyping for these
            # __validators__ fields (TODO: file an upstream PR)
            validators: list = list(origin.__validators__[name])  # type: ignore
            if name in model_class.__validators__:
                validators.extend(model_class.__validators__[name])  # type: ignore
            model_class.__validators__[name] = validators  # type: ignore

    return model_class
