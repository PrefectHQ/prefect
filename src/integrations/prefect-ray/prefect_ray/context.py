"""
Contexts to manage Ray clusters and tasks.
"""

from contextlib import contextmanager
from typing import Any, Dict

from pydantic import VERSION as PYDANTIC_VERSION

from prefect.context import ContextModel, ContextVar

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import Field
else:
    from pydantic import Field


class RemoteOptionsContext(ContextModel):
    """
    The context for Ray remote_options management.

    Attributes:
        current_remote_options: A set of current remote_options in the context.
    """

    current_remote_options: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def get(cls) -> "RemoteOptionsContext":
        """
        Return an empty `RemoteOptionsContext`
        instead of `None` if no context exists.
        """
        return cls.__var__.get(RemoteOptionsContext())

    __var__ = ContextVar("remote_options")


@contextmanager
def remote_options(**new_remote_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Context manager to add keyword arguments to Ray `@remote` calls
    for task runs. If contexts are nested, new options are merged with options
    in the outer context. If a key is present in both, the new option will be used.

    Yields:
        The current set of remote options.

    Examples:
        Use 4 CPUs and 2 GPUs for the `process` task:
        ```python
        from prefect import flow, task
        from prefect_ray.task_runners import RayTaskRunner
        from prefect_ray.context import remote_options

        @task
        def process(x):
            return x + 1

        @flow(task_runner=RayTaskRunner())
        def my_flow():
            # equivalent to setting @ray.remote(num_cpus=4, num_gpus=2)
            with remote_options(num_cpus=4, num_gpus=2):
                process.submit(42)
        ```
    """
    current_remote_options = RemoteOptionsContext.get().current_remote_options
    with RemoteOptionsContext(
        current_remote_options={**current_remote_options, **new_remote_options}
    ):
        yield
