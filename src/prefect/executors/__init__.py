"""
Prefect Executors are responsible for running tasks in a flow. During
execution of a flow run, a flow's executor will be initialized, used to execute
all tasks in the flow, then shutdown.

Currently, the available executor options are:

- `LocalExecutor`: the default, no frills executor. All tasks are executed in
    a single thread, parallelism is not supported.
- `LocalDaskExecutor`: an executor that runs on `dask` primitives with a
    using either threads or processes.
- `DaskExecutor`: the most feature-rich of the executors, this executor runs
    on `dask.distributed` and has support for distributed execution.

Which executor you choose depends on the performance requirements and
characteristics of your Flow.  See [the executors
docs](/orchestration/flow_config/executors.md) for more information.
"""
from .base import Executor
from .dask import DaskExecutor, LocalDaskExecutor
from .local import LocalExecutor

__all__ = ["DaskExecutor", "Executor", "LocalDaskExecutor", "LocalExecutor"]
