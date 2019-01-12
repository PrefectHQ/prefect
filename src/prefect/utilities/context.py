# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
This module implements the Prefect context that is available when tasks run.

Tasks can import prefect.context and access attributes that will be overwritten
when the task is run.

Example:

```python
import prefect.context
with prefect.context(a=1, b=2):
    print(prefect.context.a) # 1
print (prefect.context.a) # undefined
```
"""

import contextlib
import threading
from typing import Any, Iterator, MutableMapping

from prefect.configuration import config
from prefect.utilities.collections import DotDict


class Context(DotDict, threading.local):
    """
    A thread safe context store for Prefect data.

    The `Context` is a `DotDict` subclass, and can be instantiated the same way.

    Args:
        - *args (Any):
        - *kwargs (Any):
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if "context" in config:
            self.update(config.context)

    def __repr__(self) -> str:
        return "<Context>"

    @contextlib.contextmanager
    def __call__(self, *args: MutableMapping, **kwargs: Any) -> Iterator["Context"]:
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


context = Context()
