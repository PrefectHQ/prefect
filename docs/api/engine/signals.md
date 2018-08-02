---
sidebarDepth: 1
---

# Signals
---
 ## FAIL

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.signals.FAIL(message=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L21)</span>
Indicates that a task failed.


 ## TRIGGERFAIL

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.signals.TRIGGERFAIL(message=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L29)</span>
Indicates that a task trigger failed.


 ## SUCCESS

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.signals.SUCCESS(message=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L37)</span>
Indicates that a task succeeded.


 ## RETRY

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.signals.RETRY(message=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L45)</span>
Used to indicate that a task should be retried


 ## SKIP

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.signals.SKIP(message=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L53)</span>
Indicates that a task was skipped. By default, downstream tasks will
act as if skipped tasks succeeded.


 ## DONTRUN

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.engine.signals.DONTRUN(message=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L62)</span>
Indicates that a task should not run and its state should not be modified.


