import functools
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, TypeVar

from prefect._internal.pydantic._flags import HAS_PYDANTIC_V2, USE_V2_MODELS

T = TypeVar("T", bound=Callable[..., Any])

if TYPE_CHECKING:
    from prefect._internal.pydantic._compat import BaseModel


def model_validator(
    _func: Optional[Callable] = None,
    *,
    mode: Literal["wrap", "before", "after"] = "before",  # v2 only
) -> Any:
    """Usage docs: https://docs.pydantic.dev/2.6/concepts/validators/#model-validators

    A decorator designed for Pydantic model methods to facilitate additional validations.
    It can be applied to instance methods, class methods, or static methods of a class,
    wrapping around the designated function to inject validation logic.

    The `model_validator` does not differentiate between the types of methods it decorates
    (instance, class, or static methods). It generically wraps the given function,
    allowing the class's mechanism to determine how the method is treated
    (e.g., passing `self` for instance methods or `cls` for class methods).

    The actual handling of method types (instance, class, or static) is governed by the class
    definition itself, using Python's standard `@classmethod` and `@staticmethod` decorators
    where appropriate. This decorator simply intercepts the method call, allowing for custom
    validation logic before, after, or wrapping the original method call, depending on the
    `mode` parameter.

    !!! note Replacing Pydantic V1 `pre=True` kwarg:
    To replace a @root_validator that uses Pydantic V1's `pre=True` parameter, e.g. `@root_validator('a', pre=True)`,
    you can use the @model_validator with the `mode='before'` parameter, (and also add a check that the field is not None, if necessary).
    This will map to the `pre` parameter of `root_validator` in Pydantic V1, if the value is `True`.

    !!! note Replacing Pydantic V1 `skip_on_failure=True` kwarg:
    To replace a @root_validator that uses Pydantic V1's `skip_on_failure=True` parameter, e.g. `@root_validator('a', skip_on_failure=True)`,
    we'll simply remove it. Pydantic V2 does not have an equivalent parameter, and we use it in only 3 places in Prefect, none of which are critical.

    Args:
        _func: The function to be decorated. If None, the decorator is applied with parameters.
        mode: Specifies when the validation should occur. 'before' or 'after' are for v1 compatibility,
              'wrap' introduces v2 behavior where the validation wraps the original call.
        pre: (v1 only) If True, the validator is called before Pydantic's own validators.
        skip_on_failure: (v1 only) If True, skips validation if an earlier validation failed.

    Returns:
        The decorated function with added validation logic.

    Note:
        - The behavior of the decorator changes depending on the version of Pydantic being used.
        - The specific logic for validation should be defined within the decorated function.
    """

    def decorator(validate_func: T) -> T:
        if USE_V2_MODELS:
            from pydantic import model_validator

            return model_validator(
                mode=mode,
            )(validate_func)  # type: ignore

        elif HAS_PYDANTIC_V2:
            from pydantic.v1 import root_validator

        else:
            from pydantic import root_validator

        @functools.wraps(validate_func)
        def wrapper(
            cls: "BaseModel",
            v: Any,
        ) -> Any:
            return validate_func(cls, v)

        pre: bool = mode == "before"

        return root_validator(
            pre=pre,
        )(wrapper)  # type: ignore

    if _func is None:
        return decorator
    return decorator(_func)
