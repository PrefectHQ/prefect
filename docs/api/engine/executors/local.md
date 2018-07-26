---
sidebarDepth: 1
---

 ## LocalExecutor

### _class_ ```prefect.engine.executors.local.LocalExecutor()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/local.py#L7)</span>
An executor that runs all functions synchronously and in
the local thread.

LocalExecutors serve as their own Executor contexts.

 ####  ```prefect.engine.executors.local.LocalExecutor.submit(fn, *args, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/local.py#L15)</span>
Runs a function locally

 ####  ```prefect.engine.executors.local.LocalExecutor.wait(futures, timeout=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/executors/local.py#L21)</span>
Returns the provided futures


