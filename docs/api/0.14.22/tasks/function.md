---
sidebarDepth: 2
editLink: false
---
# Function Tasks
---
The tasks in this module can be used to represent arbitrary functions.

In general, users will not instantiate these tasks by hand; they will
automatically be applied when users apply the `@task` decorator.
 ## FunctionTask
 <div class='class-sig' id='prefect-tasks-core-function-functiontask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.function.FunctionTask</p>(fn, name=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/function.py#L14">[source]</a></span></div>

A convenience Task for functionally creating Task instances with arbitrary callable `run` methods.

**Args**:     <ul class="args"><li class="args">`fn (callable)`: the function to be the task's `run` method     </li><li class="args">`name (str, optional)`: the name of this task; if not provided it is inferred         as the function name     </li><li class="args">`**kwargs`: keyword arguments that will be passed to the Task         constructor</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the provided function violates signature requirements         for Task run methods</li></ul> **Example**: 
```python
task = FunctionTask(lambda x: x - 42, name="Subtract 42")

with Flow("My Flow") as f:
    result = task(42)

```


---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>