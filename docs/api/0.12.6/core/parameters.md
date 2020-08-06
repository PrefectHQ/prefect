---
sidebarDepth: 2
editLink: false
---
# Parameter
---
 ## Parameter
 <div class='class-sig' id='prefect-core-parameter-parameter'><p class="prefect-sig">class </p><p class="prefect-class">prefect.core.parameter.Parameter</p>(name, default=no_default, required=None, tags=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/core/parameter.py#L21">[source]</a></span></div>

A Parameter is a special task that defines a required flow input.

A parameter's "slug" is automatically -- and immutably -- set to the parameter name. Flows enforce slug uniqueness across all tasks, so this ensures that the flow has no other parameters by the same name.

**Args**:     <ul class="args"><li class="args">`name (str)`: the Parameter name.     </li><li class="args">`default (any, optional)`: A default value for the parameter.     </li><li class="args">`required (bool, optional)`: If True, the Parameter is required and the         default value is ignored. Defaults to `False` if a `default` is         provided, otherwise `True`.     </li><li class="args">`tags ([str], optional)`: A list of tags for this parameter</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-core-parameter-parameter-copy'><p class="prefect-class">prefect.core.parameter.Parameter.copy</p>(name, **task_args)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/core/parameter.py#L76">[source]</a></span></div>
<p class="methods">Creates a copy of the Parameter with a new name.<br><br>**Args**:     <ul class="args"><li class="args">`name (str)`: the new Parameter name     </li><li class="args">`**task_args (dict, optional)`: a dictionary of task attribute keyword arguments,         these attributes will be set on the new copy</li></ul>**Raises**:     <ul class="args"><li class="args">`AttributeError`: if any passed `task_args` are not attributes of the original</li></ul>**Returns**:     <ul class="args"><li class="args">`Parameter`: a copy of the current Parameter, with a new name and any attributes         updated from `task_args`</li></ul></p>|
 | <div class='method-sig' id='prefect-core-parameter-parameter-run'><p class="prefect-class">prefect.core.parameter.Parameter.run</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/core/parameter.py#L94">[source]</a></span></div>
<p class="methods">The `run()` method is called (with arguments, if appropriate) to run a task.<br><br>*Note:* The implemented `run` method cannot have `*args` in its signature. In addition, the following keywords are reserved: `upstream_tasks`, `task_args` and `mapped`.<br><br>If a task has arguments in its `run()` method, these can be bound either by using the functional API and _calling_ the task instance, or by using `self.bind` directly.<br><br>In addition to running arbitrary functions, tasks can interact with Prefect in a few ways: <ul><li> Return an optional result. When this function runs successfully,     the task is considered successful and the result (if any) can be     made available to downstream tasks. </li> <li> Raise an error. Errors are interpreted as failure. </li> <li> Raise a [signal](../engine/signals.html). Signals can include `FAIL`, `SUCCESS`,     `RETRY`, `SKIP`, etc. and indicate that the task should be put in the indicated state.         <ul>         <li> `FAIL` will lead to retries if appropriate </li>         <li> `SUCCESS` will cause the task to be marked successful </li>         <li> `RETRY` will cause the task to be marked for retry, even if `max_retries`             has been exceeded </li>         <li> `SKIP` will skip the task and possibly propogate the skip state through the             flow, depending on whether downstream tasks have `skip_on_upstream_skip=True`.         </li></ul> </li></ul></p>|
 | <div class='method-sig' id='prefect-core-parameter-parameter-serialize'><p class="prefect-class">prefect.core.parameter.Parameter.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/core/parameter.py#L107">[source]</a></span></div>
<p class="methods">Creates a serialized representation of this parameter<br><br>**Returns**:     <ul class="args"><li class="args">dict representing this parameter</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>