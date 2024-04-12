"""
Conditional decorator for fields depending on Pydantic version.
"""

import functools
from inspect import signature
from typing import TYPE_CHECKING, Any, Callable, Dict, Literal, TypeVar, Union

from typing_extensions import TypeAlias

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_V2_MODELS

FieldValidatorModes: TypeAlias = Literal["before", "after", "wrap", "plain"]
T = TypeVar("T", bound=Callable[..., Any])

if TYPE_CHECKING:
    from prefect._internal.pydantic._compat import BaseModel


def field_validator(
    field: str,
    /,
    *fields: str,
    mode: FieldValidatorModes = "after",
    check_fields: Union[bool, None] = None,
) -> Callable[[Any], Any]:
    """Usage docs: https://docs.pydantic.dev/2.7/concepts/validators/#field-validators
    Returns a decorator that conditionally applies Pydantic's `field_validator` or `validator`,
    based on the Pydantic version available, for specified field(s) of a Pydantic model.

    In Pydantic V2, it uses `field_validator` allowing more granular control over validation,
    including pre-validation and post-validation modes. In Pydantic V1, it falls back to
    using `validator`, which is less flexible but maintains backward compatibility.

    Decorate methods on the class indicating that they should be used to validate fields.

    !!! note Replacing Pydantic V1 `pre=True` kwarg:
    To replace a @validator that uses Pydantic V1's `pre` parameter, e.g. `@validator('a', pre=True)`,
    you can use `mode='before'`, e.g. @field_validator('a', mode='before').

    If a user has Pydantic V1 installed, `mode` will map to the `pre` parameter of `validator` if the value is `before`.

    !!! note Replacing Pydantic V1 `always=True` kwarg:
    To replace a @validator that uses Pydantic V1's `always` parameter, e.g. `@validator('a', always=True)`,
    you can use the @model_validator (not the @field_validator) with the `mode='before'` parameter, (and also add a check that the field is not None, if necessary).

    Read more discussion on that here: https://github.com/pydantic/pydantic/discussions/6337

    !!! note Replacing Pydantic V1 `allow_reuse=True` kwarg:
    To replace a @validator that uses Pydantic V1's `allow_reuse=True` parameter, e.g. `@validator('a', allow_reuse=True)`,
    you can simply remove the `allow_reuse` parameter when replacing the decorator, e.g. `@field_validator('a')`. This is because
    Pydantic V2 by default allows reuse of the decorated function, rendering the kwarg necessary), while Pydantic V1 required explicit
    declaration of `allow_reuse=True`.

    https://docs.pydantic.dev/2.0/migration/#the-allow_reuse-keyword-argument-is-no-longer-necessary

    Example usage:
    ```py
    from typing import Any

    from pydantic import (
        BaseModel,
        ValidationError,
        field_validator,
    )

    class Model(BaseModel):
        a: str

        @field_validator('a')
        @classmethod
        def ensure_foobar(cls, v: Any):
            if 'foobar' not in v:
                raise ValueError('"foobar" not found in a')
            return v

    print(repr(Model(a='this is foobar good')))
    #> Model(a='this is foobar good')

    try:
        Model(a='snap')
    except ValidationError as exc_info:
        print(exc_info)
        '''
        1 validation error for Model
        a
        Value error, "foobar" not found in a [type=value_error, input_value='snap', input_type=str]
        '''
    ```

        For more in depth examples, see https://docs.pydantic.dev/latest/concepts/validators/#field-validators

    Args:
        field: The first field the `field_validator` should be called on; this is separate
            from `fields` to ensure an error is raised if you don't pass at least one.
        *fields: Additional field(s) the `field_validator` should be called on.
        mode: Specifies whether to validate the fields before or after validation.
        check_fields: Whether to check that the fields actually exist on the model.

    Returns:
        A decorator that can be used to decorate a function to be used as a field_validator.

    Raises:
        PydanticUserError:
            - If `@field_validator` is used bare (with no fields).
            - If the args passed to `@field_validator` as fields are not strings.
            - If `@field_validator` applied to instance methods.
    """

    def decorator(validate_func: T) -> T:
        if USE_V2_MODELS:
            from pydantic import field_validator  # type: ignore

            return field_validator(
                field, *fields, mode=mode, check_fields=check_fields
            )(validate_func)
        elif HAS_PYDANTIC_V2:
            from pydantic.v1 import validator  # type: ignore
        else:
            from pydantic import validator

        # Extract the parameters of the validate_func function
        # e.g. if validate_func has a signature of (cls, v, values, config), we want to
        # filter the kwargs to include only those expected by validate_func, which may
        # look like (cls, v) or (cls, v, values) etc.
        validate_func_params = signature(validate_func).parameters

        @functools.wraps(validate_func)
        def wrapper(
            cls: "BaseModel",
            v: Any,
            **kwargs: Any,
        ) -> Any:
            filtered_kwargs: Dict[str, Any] = {
                k: v for k, v in kwargs.items() if k in validate_func_params
            }

            return validate_func(cls, v, **filtered_kwargs)

        # Map Pydantic V2's `mode` to Pydantic V1's `pre` parameter for use in `@validator`
        pre: bool = mode == "before"

        validator_kwargs: Dict[str, Any] = {
            "pre": pre,
            "check_fields": check_fields if check_fields is not None else True,
        }

        return validator(field, *fields, **validator_kwargs)(wrapper)  # type: ignore

    return decorator
