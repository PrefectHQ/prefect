"""
This module implements the Prefect context that is available when tasks run.

Tasks can import prefect.context and access attributes that will be overwritten
when the task is run.

Example:

```python
import prefect.context

with prefect.context(a=1, b=2):
    print(prefect.context.a) # 1

print(prefect.context.a) # undefined
```

Prefect provides various key / value pairs in context that are always available during task runs:

| Variable | Description |
| :--- | --- |
| `date` | an actual datetime object representing the current time |
| `today` | the current date formatted as `YYYY-MM-DD`|
| `today_nodash` | the current date formatted as `YYYYMMDD`|
| `yesterday` | yesterday's date formatted as `YYYY-MM-DD`|
| `yesterday_nodash` | yesterday's date formatted as `YYYYMMDD`|
| `tomorrow` | tomorrow's date formatted as `YYYY-MM-DD`|
| `tomorrow_nodash` | tomorrow's date formatted as `YYYYMMDD`|
| `logger` | the logger for the current task |
| `config` | the complete [Prefect configuration]\
(https://docs.prefect.io/core/concepts/configuration.html) object that is being used \
during this run |
| `flow_name` | the name of the current flow |
| `scheduled_start_time` | \
a datetime object representing the scheduled start time for the flow run; \
falls back to `now` for unscheduled runs |
| `parameters` | a dictionary of parameter values for the current flow run |
| `map_index` | the map index of the current task (if mapped, otherwise `None`) |
| `task_name` | the name of the current task |
| `task_full_name` | the name of the current task, including map index |
| `task_slug` | the slug of the current task |
| `task_tags` | the tags on the current task |
| `task_run_count` | the run count of the task run - typically only interesting for retrying tasks |
| `task_loop_count` | if the Task utilizes looping, the loop count of the task run |
| `task_loop_result` | if the Task is looping, the current loop result |

In addition, Prefect Cloud supplies some additional context variables:

| Variable | Description |
| :--- | --- |
| `flow_id` | the id of the current flow |
| `flow_run_id` | the id of the current flow run |
| `flow_run_version` | the state version of the current flow run |
| `flow_run_name` | the name of the current flow run |
| `task_id` | the id of the current task |
| `task_run_id` | the id of the current task run |
| `task_run_version` | the state version of the current task run |

Users can also provide values to context at runtime. For more information, see
the [Context concept
doc](https://docs.prefect.io/core/concepts/execution.html#context).
"""

import contextlib
import threading
from typing import Any, Iterator, MutableMapping

from prefect.configuration import config
from prefect.utilities.collections import DotDict, merge_dicts


class Context(DotDict, threading.local):
    """
    A thread safe context store for Prefect data.

    The `Context` is a `DotDict` subclass, and can be instantiated the same way.

    Args:
        - *args (Any): arguments to provide to the `DotDict` constructor (e.g.,
            an initial dictionary)
        - **kwargs (Any): any key / value pairs to initialize this context with
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if "context" in config:
            self.update(config.context)
        self["config"] = merge_dicts(config, self.get("config", {}))  # order matters

    def __getstate__(self) -> None:
        """
        Because we dynamically update context during runs, we don't ever want to pickle
        or "freeze" the contents of context.  Consequently it should always be accessed
        as an attribute of the prefect module.
        """
        raise TypeError(
            "Pickling context objects is explicitly not supported. You should always "
            "access context as an attribute of the `prefect` module, as in `prefect.context`"
        )

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
            new_context = dict(*args, **kwargs)
            if "config" in new_context:
                new_context["config"] = merge_dicts(
                    self.get("config", {}), new_context["config"]
                )
            self.update(new_context)  # type: ignore
            yield self
        finally:
            self.clear()
            self.update(previous_context)


context = Context()
