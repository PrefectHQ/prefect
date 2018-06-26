"""
This module implements the Prefect context that is available when tasks run.

Tasks can import prefect.context and access attributes that will be overwritten
when the task is run.

Example:
    import prefect.context
    with prefect.context(a=1, b=2):
        print(prefect.context.a) # 1
    print (prefect.context.a) # undefined

"""

import contextlib
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Union, Iterator


from prefect.utilities.json import Serializable

DictOrContextType = Union[dict, "PrefectContext"]

# context dictionary
class PrefectContext(SimpleNamespace, Serializable):
    """
    A context store for Prefect data.
    """

    _context = None

    # PrefectContext is a Singleton
    def __new__(cls, *args: DictOrContextType, **kwargs: Any) -> "PrefectContext":
        if not cls._context:
            cls._context = super().__new__(cls, *args, **kwargs)
        return cls._context

    def __init__(self, *args: DictOrContextType, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.update(*args)

    def __repr__(self) -> str:
        return "<Prefect Context>"

    def __delattr__(self, key: str) -> None:
        del self.__dict__[key]

    def __iter__(self) -> Iterable:
        return iter(self.__dict__.keys())

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def update(self, *args: DictOrContextType, **kwargs: Any) -> None:
        for a in args:
            if isinstance(a, PrefectContext):
                a = a.to_dict()
            self.__dict__.update(a)
        self.__dict__.update(kwargs)

    def clear(self) -> None:
        self.__dict__.clear()

    @contextlib.contextmanager
    def __call__(
        self, *args: DictOrContextType, **kwargs: Any
    ) -> Iterator["PrefectContext"]:
        """
        A context manager for setting / resetting the Prefect context

        Example:
            import prefect.context
            with prefect.context(dict(a=1, b=2), c=3):
                print(prefect.context.a) # 1
        """
        previous_context = self.__dict__.copy()
        try:
            self.update(*args, **kwargs)
            yield self
        finally:
            self.clear()
            self.update(previous_context)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def setdefault(self, key: str, default: Any) -> Any:
        if key not in self:
            self.key = default
        return getattr(self, key)


context = PrefectContext()
