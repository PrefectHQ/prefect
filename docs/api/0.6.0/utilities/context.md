---
sidebarDepth: 2
editLink: false
---
# Context
---
This module implements the Prefect context that is available when tasks run.

Tasks can import prefect.context and access attributes that will be overwritten
when the task is run.

Example:

```python
import prefect.context

with prefect.context(a=1, b=2):
    print(prefect.context.a) # 1

print(prefect.context.a) # undefined
```

Prefect provides various key / value pairs in context that are always available during task runs:

| Variable | Description |
| :--- | --- |
| `scheduled_start_time` | an actual datetime object representing the scheduled start time for the Flow run; falls back to `now` for unscheduled runs |
| `date` | an actual datetime object representing the current time |
| `today` | the current date formatted as `YYYY-MM-DD`|
| `today_nodash` | the current date formatted as `YYYYMMDD`|
| `yesterday` | yesterday's date formatted as `YYYY-MM-DD`|
| `yesterday_nodash` | yesterday's date formatted as `YYYYMMDD`|
| `tomorrow` | tomorrow's date formatted as `YYYY-MM-DD`|
| `tomorrow_nodash` | tomorrow's date formatted as `YYYYMMDD`|
| `task_name` | the name of the current task |

Users can also provide values to context at runtime.
 ## Context
 <div class='class-sig' id='prefect-utilities-context-context'><p class="prefect-sig">class </p><p class="prefect-class">prefect.utilities.context.Context</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/utilities/context.py#L43">[source]</a></span></div>

A thread safe context store for Prefect data.

The `Context` is a `DotDict` subclass, and can be instantiated the same way.

**Args**:     <ul class="args"><li class="args">`*args (Any)`: arguments to provide to the `DotDict` constructor (e.g.,         an initial dictionary)     </li><li class="args">`**kwargs (Any)`: any key / value pairs to initialize this context with</li></ul>


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 16, 2019 at 04:54 UTC</p>