from typing import Any, Callable, Literal, cast

from typing_extensions import TypeAlias

from prefect._internal.pydantic._flags import (
    HAS_PYDANTIC_V2,
    USE_PYDANTIC_V2,
)

FieldValidatorModes: TypeAlias = Literal["before", "after", "wrap", "plain"]

if HAS_PYDANTIC_V2 and not USE_PYDANTIC_V2:
    from pydantic import model_validator  # type: ignore
else:
    if HAS_PYDANTIC_V2:
        from pydantic.v1 import root_validator  # type: ignore
    else:
        from pydantic import root_validator  # type: ignore

    def model_validator(
        *args: Any,
        mode: Literal["wrap", "before", "after"],
    ) -> Any:
        def _inner(func: Callable[..., Any]) -> Any:
            if isinstance(func, classmethod):
                func = cast(Callable[..., Any], getattr(func, "__func__"))
            deco = root_validator(  # type: ignore [call-overload]
                pre=mode == "before",
                allow_reuse=True,
                skip_on_failure=False,  # type: ignore [call-overload]
            )
            return deco(func)  # type: ignore

        return _inner


__all__ = ["model_validator"]
