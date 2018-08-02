---
sidebarDepth: 1
---

 ## DaskExecutor

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.executors.dask.DaskExecutor()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/dask.py#L12)</span>
A class that automatically uses a specified JSONCodec to serialize itself.

 ####  ```prefect.engine.executors.dask.DaskExecutor.start()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/dask.py#L13)</span>
Any initialization this executor needs to perform should be done in this
context manager, and torn down after yielding.

 ####  ```prefect.engine.executors.dask.DaskExecutor.submit(fn, *args, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/dask.py#L22)</span>
Submit a function to the executor for execution. Returns a future

 ####  ```prefect.engine.executors.dask.DaskExecutor.wait(futures, timeout=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/dask.py#L28)</span>
Resolves futures to their values. Blocks until the future is complete.


