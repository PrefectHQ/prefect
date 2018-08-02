---
sidebarDepth: 1
---

 ## Executor

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.executors.base.Executor()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/base.py#L14)</span>
A class that automatically uses a specified JSONCodec to serialize itself.

 ####  ```prefect.engine.executors.base.Executor.start()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/base.py#L18)</span>
Any initialization this executor needs to perform should be done in this
context manager, and torn down after yielding.

 ####  ```prefect.engine.executors.base.Executor.submit(fn, *args, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/base.py#L26)</span>
Submit a function to the executor for execution. Returns a future

 ####  ```prefect.engine.executors.base.Executor.submit_with_context(fn, *args, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/base.py#L38)</span>
Submit a function to the executor that will be run in a specific Prefect context.

Returns a Any.

 ####  ```prefect.engine.executors.base.Executor.wait(futures, timeout=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/base.py#L32)</span>
Resolves futures to their values. Blocks until the future is complete.


