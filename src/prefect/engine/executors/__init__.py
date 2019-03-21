"""
Prefect Executors implement the logic for how Tasks are run. The standard interface
for an Executor consists of the following methods:

- `submit(fn, *args, **kwargs)`: submit `fn(*args, **kwargs)` for execution;
    note that this function is (in general) non-blocking, meaning that `executor.submit(...)`
    will _immediately_ return a future-like object regardless of whether `fn(*args, **kwargs)`
    has completed running
- `wait(object)`: resolves any objects returned by `executor.submit` to
    their values; this function _will_ block until execution of `object` is complete
- `map(fn, *args, upstream_states, **kwargs)`: submit function to be mapped
    over based on the edge information contained in `upstream_states`.  Any "mapped" Edge
    will be converted into multiple function submissions, one for each value of the upstream mapped tasks.

Currently, the available executor options are:

- `LocalExecutor`: the no frills, straightforward executor - great for simple
    debugging; tasks are executed immediately upon being called by `executor.submit()`.
- `SynchronousExecutor`: an executor that runs on `dask` primitives with the
    synchronous dask scheduler; currently the default executor
- `DaskExecutor`: the most feature-rich of the executors, this executor runs
    on `dask.distributed` and has support for multiprocessing, multithreading, and distributed execution.

Which executor you choose depends on whether you intend to use things like parallelism
of task execution.
"""
import prefect
from prefect.engine.executors.base import Executor
from prefect.engine.executors.dask import DaskExecutor
from prefect.engine.executors.local import LocalExecutor
from prefect.engine.executors.sync import SynchronousExecutor
