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
from typing import Any, Iterator, MutableMapping

from prefect.utilities.collections import DotDict


class PrefectContext(DotDict):
    """
    A context store for Prefect data.
    """

    def __repr__(self) -> str:
        return "<Prefect Context>"

    @contextlib.contextmanager
    def __call__(
        self, *args: MutableMapping, **kwargs: Any
    ) -> Iterator["PrefectContext"]:
        """
        A context manager for setting / resetting the Prefect context

        Example:
            import prefect.context
            with prefect.context(dict(a=1, b=2), c=3):
                print(prefect.context.a) # 1
        """
        previous_context = self.copy()
        try:
            self.update(*args, **kwargs)
            yield self
        finally:
            self.clear()
            self.update(previous_context)


context = PrefectContext()
