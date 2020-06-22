"""
Prefect Executors implement the logic for how Tasks are run. The standard interface
for an Executor consists of the following methods:

- `submit(fn, *args, **kwargs)`: submit `fn(*args, **kwargs)` for execution;
    note that this function is (in general) non-blocking, meaning that `executor.submit(...)`
    will _immediately_ return a future-like object regardless of whether `fn(*args, **kwargs)`
    has completed running
- `wait(object)`: resolves any objects returned by `executor.submit` to
    their values; this function _will_ block until execution of `object` is complete

Currently, the available executor options are:

- `LocalExecutor`: the no frills, straightforward executor - great for debugging;
    tasks are executed immediately upon being called by `executor.submit()`.Note
    that the `LocalExecutor` is not capable of parallelism.  Currently the default executor.
- `LocalDaskExecutor`: an executor that runs on `dask` primitives with a
    configurable dask scheduler.
- `DaskExecutor`: the most feature-rich of the executors, this executor runs
    on `dask.distributed` and has support for multiprocessing, multithreading, and distributed execution.

Which executor you choose depends on whether you intend to use things like parallelism
of task execution.

The key difference between the `LocalDaskExecutor` and the `DaskExecutor` is the choice
of scheduler. The `LocalDaskExecutor` is configurable to use
[any number of schedulers](https://docs.dask.org/en/latest/scheduler-overview.html) while the
`DaskExecutor` uses the [distributed scheduler](https://docs.dask.org/en/latest/scheduling.html).
This means that the `LocalDaskExecutor` can help achieve some multithreading / multiprocessing
however it does not provide as many distributed features as the `DaskExecutor`.

"""
import prefect
from prefect.engine.executors.base import Executor
from prefect.engine.executors.dask import DaskExecutor, LocalDaskExecutor
from prefect.engine.executors.local import LocalExecutor
