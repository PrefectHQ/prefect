from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from click import Option


def add_options(options: List["Option"]):
    """A decorator for adding a list of options to a click command"""

    def decorator(func):
        for opt in reversed(options):
            func = opt(func)
        return func

    return decorator
