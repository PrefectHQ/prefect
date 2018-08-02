---
sidebarDepth: 1
---

# Task Utilities
---
 ###  ```prefect.utilities.tasks.group(name, append=False)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/utilities/tasks.py#L12)</span>
Context manager for setting a task group.


 ###  ```prefect.utilities.tasks.tags(*tags)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/utilities/tasks.py#L25)</span>
Context manager for setting task tags.


 ###  ```prefect.utilities.tasks.as_task(x)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/utilities/tasks.py#L36)</span>
Wraps a function, collection, or constant with the appropriate Task type.


 ###  ```prefect.utilities.tasks.task(fn, *task_init_kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/utilities/tasks.py#L66)</span>
A decorator for creating Tasks from functions.

Usage:

```python
@task(name='hello', retries=3)
def hello(name):
    print('hello, {}'.format(name))

with Flow() as flow:
    t1 = hello('foo')
    t2 = hello('bar')
```


