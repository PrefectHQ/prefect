import functools
from typing import Any, Callable, Literal, Optional, TypeVar

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_V2_MODELS

T = TypeVar("T", bound=Callable[..., Any])


def model_validator(
    _func: Optional[Callable] = None,
    *,
    mode: Literal["wrap", "before", "after"] = "before",  # v2 only
    pre: bool = False,  # v1 only
    skip_on_failure: bool = False,  # v1 only
) -> Any:
    """Usage docs: https://docs.pydantic.dev/2.6/concepts/validators/#model-validators

    Decorate model methods for validation purposes.

    Example usage:
    ```py
    from typing_extensions import Self

    from pydantic import BaseModel, ValidationError, model_validator

    class Square(BaseModel):
        width: float
        height: float

        @model_validator(mode='after')
        def verify_square(self) -> Self:
            if self.width != self.height:
                raise ValueError('width and height do not match')
            return self

    s = Square(width=1, height=1)
    print(repr(s))
    #> Square(width=1.0, height=1.0)

    try:
        Square(width=1, height=2)
    except ValidationError as e:
        print(e)
        '''
        1 validation error for Square
          Value error, width and height do not match [type=value_error, input_value={'width': 1, 'height': 2}, input_type=dict]
        '''
    ```

    For more in depth examples, see [Model Validators](../concepts/validators.md#model-validators).

    Args:
        mode: A required string literal that specifies the validation mode.
            It can be one of the following: 'wrap', 'before', or 'after'.
            'wrap' is only available in Pydantic v2.

        pre: A boolean that specifies whether the validator should be called before the standard validators.
            Defaults to False.

        skip_on_failure: A boolean that specifies whether the validator should be skipped if it fails.
            Defaults to False.

    Returns:
        A decorator that can be used to decorate a function to be used as a model validator.
    """

    def decorator(validate_func: T) -> T:
        if USE_V2_MODELS:
            from pydantic import model_validator

            return model_validator(
                mode=mode,
            )(validate_func)  # type: ignore

        elif HAS_PYDANTIC_V2:
            from pydantic.v1 import BaseModel, root_validator

        else:
            # use the v1 root_validator imported regular not from .v1
            from pydantic import BaseModel, root_validator

        @functools.wraps(validate_func)
        def wrapper(
            cls: "BaseModel",
            v: Any,
        ) -> Any:
            return validate_func(cls, v)

        return root_validator(pre=pre, skip_on_failure=skip_on_failure)(wrapper)  # type: ignore

    if _func is None:
        return decorator
    return decorator(_func)
