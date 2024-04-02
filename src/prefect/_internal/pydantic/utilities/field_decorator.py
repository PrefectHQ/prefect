"""
Conditional decorator for fields depending on Pydantic version.
"""

from typing import Any, Callable, Literal, Union

from typing_extensions import TypeAlias

from prefect._internal.pydantic._flags import USE_V2_MODELS

FieldValidatorModes: TypeAlias = Literal["before", "after", "wrap", "plain"]


def my_field_validator(
    field: str,
    /,
    *fields: str,
    mode: FieldValidatorModes = "after",  # v2 only
    check_fields: Union[bool, None] = None,
    pre=False,  # v1 only
    always=False,  # v1 only
    allow_reuse=False,  # v1 only
) -> Callable[[Any], Any]:
    """Usage docs: https://docs.pydantic.dev/2.7/concepts/validators/#field-validators
    Returns a decorator that conditionally applies Pydantic's `field_validator` or `validator`,
    based on the Pydantic version available, for specified field(s) of a Pydantic model.

    In Pydantic V2, it uses `field_validator` allowing more granular control over validation,
    including pre-validation and post-validation modes. In Pydantic V1, it falls back to
    using `validator`, which is less flexible but maintains backward compatibility.

    Decorate methods on the class indicating that they should be used to validate fields.

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

        For more in depth examples, see [Field Validators](../concepts/validators.md#field-validators).

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

    def decorator(validate_func):
        if USE_V2_MODELS:
            from pydantic import field_validator

            def wrapper(cls, v, info):
                values = info.data
                return validate_func(cls, v, values)

            return field_validator(
                field, *fields, mode=mode, check_fields=check_fields
            )(wrapper)
        else:
            from pydantic.v1 import validator

            # the following are the arguments that we currently use in our Pydantic v1 validator
            return validator(
                field,
                *fields,
                pre=pre,
                always=always,
                check_fields=check_fields if check_fields is not None else True,
                allow_reuse=allow_reuse,
            )(validate_func)

    return decorator
