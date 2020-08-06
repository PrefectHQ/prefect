---
sidebarDepth: 2
editLink: false
---
# Control Flow Tasks
---
 ## FilterTask
 <div class='class-sig' id='prefect-tasks-control-flow-filter-filtertask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.control_flow.filter.FilterTask</p>(filter_func=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/filter.py#L8">[source]</a></span></div>

Task for filtering lists of results.  The default filter removes `NoResult`s, `None`s and Exceptions, intended to be used for filtering out mapped results.  Note that this task has a default trigger of `all_finished` and `skip_on_upstream_skip=False`.

**Args**:     <ul class="args"><li class="args">`filter_func (Callable, optional)`: a function to use for filtering         results; this function should accept a single positional argument and return a boolean         indicating whether this result should be _kept_ or not.  The default is         to filter out `NoResult`s and Exceptions     </li><li class="args">`**kwargs (optional)`: additional keyword arguments to pass to the Task         constructor</li></ul>**Example**:


```python
from prefect import task, Flow
from prefect.tasks.control_flow import FilterTask

default_filter = FilterTask()
even_filter = FilterTask(filter_func=lambda x: x % 2 == 0)

@task
def add(x):
    return x + 1

@task
def div(x):
    return 1 / x

with Flow("filter-numbers") as flow:
    even_numbers = even_filter(add.map(x=[-1, 0, 1, 2, 3, 99, 314]))
    final_numbers = default_filter(div.map(even_numbers))

flow_state = flow.run()

print(flow_state.result[final_numbers].result)
# [0.5, 0.25, 0.01]

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-control-flow-filter-filtertask-run'><p class="prefect-class">prefect.tasks.control_flow.filter.FilterTask.run</p>(task_results)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/filter.py#L58">[source]</a></span></div>
<p class="methods">Task run method.<br><br>**Args**:     <ul class="args"><li class="args">`task_results (List[Any])`: a list of results from upstream tasks,         which will be filtered using `self.filter_func`</li></ul>**Returns**:     <ul class="args"><li class="args">`List[Any]`: a filtered list of results</li></ul></p>|

---
<br>

 ## case
 <div class='class-sig' id='prefect-tasks-control-flow-case-case'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.control_flow.case.case</p>(task, value)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/case.py#L12">[source]</a></span></div>

A conditional block in a flow definition.

Used as a context-manager, ``case`` creates a block of tasks that are only run if the result of ``task`` is equal to ``value``.

**Args**:     <ul class="args"><li class="args">`task (Task)`: The task to use in the comparison     </li><li class="args">`value (Any)`: A constant the result of ``task`` will be compared with</li></ul>**Example**:

A ``case`` block is similar to Python's if-blocks. It delimits a block of tasks that will only be run if the result of ``task`` is equal to ``value``:


```python
# Standard python code
if task == value:
    res = run_if_task_equals_value()
    other_task(res)

# Equivalent prefect code
with case(task, value):
    # Tasks created in this block are only run if the
    # result of ``task`` is equal to ``value``
    res = run_if_task_equals_value()
    other_task(run)

```

The ``value`` argument can be any non-task object. Here we branch on a string result:


```python
with Flow("example") as flow:
    cond = condition()

    with case(cond, "a"):
        run_if_cond_is_a()

    with case(cond, "b"):
        run_if_cond_is_b()

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-control-flow-case-case-add-task'><p class="prefect-class">prefect.tasks.control_flow.case.case.add_task</p>(task, flow)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/case.py#L66">[source]</a></span></div>
<p class="methods">Add a new task under the case statement.<br><br>**Args**:     <ul class="args"><li class="args">`task (Task)`: the task to add     </li><li class="args">`flow (Flow)`: the flow to use</li></ul></p>|

---
<br>


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-control-flow-conditional-switch'><p class="prefect-class">prefect.tasks.control_flow.conditional.switch</p>(condition, cases, mapped=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/conditional.py#L52">[source]</a></span></div>
<p class="methods">Adds a SWITCH to a workflow.<br><br>The condition task is evaluated and the result is compared to the keys of the cases dictionary. The task corresponding to the matching key is run; all other tasks are skipped. Any tasks downstream of the skipped tasks are also skipped unless they set `skip_on_upstream_skip=False`.<br><br>**Example**: <br><pre class="language-python"><code class="language-python"><span class="token decorator">@task</span><br><span class="token keyword">def</span> <span class="token function">condition</span><span class="token punctuation">(</span><span class="token punctuation">)</span><span class="token punctuation">:</span><br>    <span class="token keyword">return</span> <span class="token string">"</span><span class="token string">b</span><span class="token string">"</span>    <span class="token comment"># returning 'b' will take the b_branch</span><br><br><span class="token decorator">@task</span><br><span class="token keyword">def</span> <span class="token function">a_branch</span><span class="token punctuation">(</span><span class="token punctuation">)</span><span class="token punctuation">:</span><br>    <span class="token keyword">return</span> <span class="token string">"</span><span class="token string">A Branch</span><span class="token string">"</span><br><br><span class="token decorator">@task</span><br><span class="token keyword">def</span> <span class="token function">b_branch</span><span class="token punctuation">(</span><span class="token punctuation">)</span><span class="token punctuation">:</span><br>    <span class="token keyword">return</span> <span class="token string">"</span><span class="token string">B Branch</span><span class="token string">"</span><br><br><span class="token keyword">with</span> Flow<span class="token punctuation">(</span><span class="token string">"</span><span class="token string">switch-flow</span><span class="token string">"</span><span class="token punctuation">)</span> <span class="token keyword">as</span> flow<span class="token punctuation">:</span><br>    switch<span class="token punctuation">(</span>condition<span class="token punctuation">,</span> <span class="token builtin">dict</span><span class="token punctuation">(</span>a<span class="token operator">=</span>a_branch<span class="token punctuation">,</span> b<span class="token operator">=</span>b_branch<span class="token punctuation">)</span><span class="token punctuation">)</span><br></code></pre><br><br><br>**Args**:     <ul class="args"><li class="args">`condition (Task)`: a task whose result forms the condition for the switch     </li><li class="args">`cases (Dict[Any, Task])`: a dict representing the "case" statements of the switch.         The value of the `condition` task will be compared to the keys of this dict, and         the matching task will be executed.     </li><li class="args">`mapped (bool, optional)`: If true, the `switch` operation will be mapped over the         arguments instead of applied directly. Defaults to `False`.</li></ul>**Raises**:     <ul class="args"><li class="args">`PrefectWarning`: if any of the tasks in "cases" have upstream dependencies,         then this task will warn that those upstream tasks may run whether or not the         switch condition matches their branch. The most common cause of this is passing a         list of tasks as one of the cases, which adds the `List` task to the switch         condition but leaves the tasks themselves upstream.</li></ul></p>|
 | <div class='method-sig' id='prefect-tasks-control-flow-conditional-ifelse'><p class="prefect-class">prefect.tasks.control_flow.conditional.ifelse</p>(condition, true_task, false_task, mapped=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/conditional.py#L104">[source]</a></span></div>
<p class="methods">Builds a conditional branch into a workflow.<br><br>If the condition evaluates True(ish), the true_task will run. If it evaluates False(ish), the false_task will run. The task doesn't run is Skipped, as are all downstream tasks that don't set `skip_on_upstream_skip=False`.<br><br>**Args**:     <ul class="args"><li class="args">`condition (Task)`: a task whose boolean result forms the condition for the ifelse     </li><li class="args">`true_task (Task)`: a task that will be executed if the condition is True     </li><li class="args">`false_task (Task)`: a task that will be executed if the condition is False     </li><li class="args">`mapped (bool, optional)`: If true, the `ifelse` operation will be mapped over the         arguments instead of applied directly. Defaults to `False`.</li></ul></p>|
 | <div class='method-sig' id='prefect-tasks-control-flow-conditional-merge'><p class="prefect-class">prefect.tasks.control_flow.conditional.merge</p>(*tasks, flow=None, mapped=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/control_flow/conditional.py#L132">[source]</a></span></div>
<p class="methods">Merges conditional branches back together.<br><br>A conditional branch in a flow results in one or more tasks proceeding and one or more tasks skipping. It is often convenient to merge those branches back into a single result. This function is a simple way to achieve that goal. By default this task will skip if all its upstream dependencies are also skipped.<br><br>The merge will return the first real result it encounters, or `None`. If multiple tasks might return a result, group them with a list.<br><br>**Example**:     <br><pre class="language-python"><code class="language-python">    <span class="token keyword">with</span> Flow<span class="token punctuation">(</span><span class="token string">"</span><span class="token string">My Flow</span><span class="token string">"</span><span class="token punctuation">)</span><span class="token punctuation">:</span><br>        true_branch <span class="token operator">=</span> ActionIfTrue<span class="token punctuation">(</span><span class="token punctuation">)</span><br>        false_branch <span class="token operator">=</span> ActionIfFalse<span class="token punctuation">(</span><span class="token punctuation">)</span><br>        ifelse<span class="token punctuation">(</span>CheckCondition<span class="token punctuation">(</span><span class="token punctuation">)</span><span class="token punctuation">,</span> true_branch<span class="token punctuation">,</span> false_branch<span class="token punctuation">)</span><br><br>        merged_result <span class="token operator">=</span> merge<span class="token punctuation">(</span>true_branch<span class="token punctuation">,</span> false_branch<span class="token punctuation">)</span><br>    <br></code></pre><br><br><br>**Args**:     <ul class="args"><li class="args">`*tasks (Task)`: tasks whose results should be merged into a single result. The tasks are         assumed to all sit downstream of different `switch` branches, such that only         one of them will contain a result and the others will all be skipped.     </li><li class="args">`flow (Flow, optional)`: The flow to use, defaults to the current flow         in context if no flow is specified     </li><li class="args">`mapped (bool, optional)`: If true, the `merge` operation will be mapped over the         arguments instead of applied directly. Defaults to `False`.</li></ul>**Returns**:     <ul class="args"><li class="args">`Task`: a Task representing the merged result.</li></ul></p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on August 6, 2020 at 13:56 UTC</p>