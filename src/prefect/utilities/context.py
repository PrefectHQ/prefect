# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/beta-eula

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

Prefect provides various key / value pairs in context that are always available during task runs:

| Variable | Description |
| :--- | --- |
| `scheduled_start_time` | an actual datetime object representing the scheduled start time for the Flow run; falls back to `now` for unscheduled runs |
| `date` | an actual datetime object representing the current time |
| `today` | the current date formatted as `YYYY-MM-DD`|
| `today_nodash` | the current date formatted as `YYYYMMDD`|
| `yesterday` | yesterday's date formatted as `YYYY-MM-DD`|
| `yesterday_nodash` | yesterday's date formatted as `YYYYMMDD`|
| `tomorrow` | tomorrow's date formatted as `YYYY-MM-DD`|
| `tomorrow_nodash` | tomorrow's date formatted as `YYYYMMDD`|
| `task_name` | the name of the current task |
"""

import contextlib
import pendulum
import threading
from typing import Any, Iterator, MutableMapping

from prefect.configuration import config
from prefect.utilities.collections import DotDict


class Context(DotDict, threading.local):
    """
    A thread safe context store for Prefect data.

    The `Context` is a `DotDict` subclass, and can be instantiated the same way.

    Args:
        - *args (Any): arguments to provide to the `DotDict` constructor (e.g.,
            an initial dictionary)
        - *kwargs (Any): any key / value pairs to initialize this context with
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if "context" in config:
            self.update(config.context)

        # add various formatted dates to context
        now = pendulum.now("utc")
        dates = {
            "date": now,
            "today": now.strftime("%Y-%m-%d"),
            "yesterday": now.add(days=-1).strftime("%Y-%m-%d"),
            "tomorrow": now.add(days=1).strftime("%Y-%m-%d"),
            "today_nodash": now.strftime("%Y%m%d"),
            "yesterday_nodash": now.add(days=-1).strftime("%Y%m%d"),
            "tomorrow_nodash": now.add(days=1).strftime("%Y%m%d"),
        }
        self.update(dates)

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
