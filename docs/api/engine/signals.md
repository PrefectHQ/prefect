---
sidebarDepth: 1
---

# Signals
---
 ### _class_ ```prefect.engine.signals.FAIL(message=None, data=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L21)</span>
Indicates that a task failed.


 ### _class_ ```prefect.engine.signals.TRIGGERFAIL(message=None, data=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L29)</span>
Indicates that a task trigger failed.


 ### _class_ ```prefect.engine.signals.SUCCESS(message=None, data=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L37)</span>
Indicates that a task succeeded.


 ### _class_ ```prefect.engine.signals.RETRY(message=None, data=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L45)</span>
Used to indicate that a task should be retried


 ### _class_ ```prefect.engine.signals.SKIP(message=None, data=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L53)</span>
Indicates that a task was skipped. By default, downstream tasks will
act as if skipped tasks succeeded.


 ### _class_ ```prefect.engine.signals.DONTRUN(message=None, data=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/engine/signals.py#L62)</span>
Indicates that a task should not run and its state should not be modified.


