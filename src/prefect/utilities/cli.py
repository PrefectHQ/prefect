from typing import TYPE_CHECKING, List, Callable

if TYPE_CHECKING:
    from click import Option


def add_options(options: List["Option"]) -> Callable:
    """A decorator for adding a list of options to a click command"""

    def decorator(func: Callable) -> Callable:
        for opt in reversed(options):
            func = opt(func)  # type: ignore
        return func

    return decorator
