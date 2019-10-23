---
sidebarDepth: 2
editLink: false
---
# Constant Tasks
---
The tasks in this module can be used to represent constant values.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users create dependencies between a task and a constant value.

Constant tasks are most commonly used to prevent Prefect from creating a large number
of auto-generated tasks in Python collections.  For example,

```python
from prefect import task, Flow
from prefect.tasks.core.constants import Constant

@task
def do_nothing(values):
    return values

with Flow("Many Small Tasks") as large_flow:
    result = do_nothing({"x": 1, "z": 99})

large_flow.tasks
#    {<Task: 'x'>,
#     <Task: 'z'>,
#     <Task: 1>,
#     <Task: 99>,
#     <Task: Dict>,
#     <Task: List>,
#     <Task: List>,
#     <Task: do_nothing>}

with Flow("Two Tasks") as small_flow:
    result = do_nothing(Constant({"x": 1, "z": 99}))

small_flow.tasks
# {<Task: Constant[dict]>, <Task: do_nothing>}
```
 ## Constant
 <div class='class-sig' id='prefect-tasks-core-constants-constant'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.constants.Constant</p>(value, name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/constants.py#L44">[source]</a></span></div>

The Constant class represents a single value in the flow graph.

**Args**:     <ul class="args"><li class="args">`value (Any)`: a constant value     </li><li class="args">`name (str)`: a name for the constant; defaults to "Constant[(type(value))]"         if not provided     </li><li class="args">`**kwargs (Any)`: kwargs to pass to the Task constructor</li></ul>Constant tasks are most commonly used to prevent Prefect from creating a large number of auto-generated tasks in Python collections.

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-core-constants-constant-run'><p class="prefect-class">prefect.tasks.core.constants.Constant.run</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/constants.py#L69">[source]</a></span></div>
<p class="methods">The `run()` method is called (with arguments, if appropriate) to run a task.<br><br>*Note:* The implemented `run` method cannot have `*args` in its signature. In addition, the following keywords are reserved: `upstream_tasks`, `task_args` and `mapped`.<br><br>If a task has arguments in its `run()` method, these can be bound either by using the functional API and _calling_ the task instance, or by using `self.bind` directly.<br><br>In addition to running arbitrary functions, tasks can interact with Prefect in a few ways: <ul><li> Return an optional result. When this function runs successfully,     the task is considered successful and the result (if any) can be     made available to downstream tasks. </li> <li> Raise an error. Errors are interpreted as failure. </li> <li> Raise a [signal](../engine/signals.html). Signals can include `FAIL`, `SUCCESS`, `RETRY`, `SKIP`, etc.     and indicate that the task should be put in the indicated state.         <ul>         <li> `FAIL` will lead to retries if appropriate </li>         <li> `SUCCESS` will cause the task to be marked successful </li>         <li> `RETRY` will cause the task to be marked for retry, even if `max_retries`             has been exceeded </li>         <li> `SKIP` will skip the task and possibly propogate the skip state through the             flow, depending on whether downstream tasks have `skip_on_upstream_skip=True`. </li></ul> </li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on October 17, 2019 at 13:42 UTC</p>