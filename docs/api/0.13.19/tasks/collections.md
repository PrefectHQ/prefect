---
sidebarDepth: 2
editLink: false
---
# Collection Tasks
---
The tasks in this module can be used to represent collections of task results, such as
lists, tuples, sets, and dictionaries.

In general, users will not instantiate these tasks by hand; they will automatically be
applied when users create dependencies between a task and a collection of other objects.
 ## List
 <div class='class-sig' id='prefect-tasks-core-collections-list'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.collections.List</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L53">[source]</a></span></div>

Collects task results into a list.

**Args**:     <ul class="args"><li class="args">`*args (Any)`: positional arguments for the `Task` class     </li><li class="args">`**kwargs (Any)`: keyword arguments for the `Task` class</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-core-collections-list-run'><p class="prefect-class">prefect.tasks.core.collections.List.run</p>(**task_results)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L65">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`**task_results (Any)`: task results to collect into a list</li></ul> **Returns**:     <ul class="args"><li class="args">`list`: a list of task results</li></ul></p>|

---
<br>

 ## Tuple
 <div class='class-sig' id='prefect-tasks-core-collections-tuple'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.collections.Tuple</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L84">[source]</a></span></div>

Collects task results into a tuple.

**Args**:     <ul class="args"><li class="args">`*args (Any)`: positional arguments for the `Task` class     </li><li class="args">`**kwargs (Any)`: keyword arguments for the `Task` class</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-core-collections-tuple-run'><p class="prefect-class">prefect.tasks.core.collections.Tuple.run</p>(**task_results)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L96">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`**task_results (Any)`: task results to collect into a tuple</li></ul> **Returns**:     <ul class="args"><li class="args">`tuple`: a tuple of task results</li></ul></p>|

---
<br>

 ## Set
 <div class='class-sig' id='prefect-tasks-core-collections-set'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.collections.Set</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L117">[source]</a></span></div>

Collects task results into a set.

**Args**:     <ul class="args"><li class="args">`*args (Any)`: positional arguments for the `Task` class     </li><li class="args">`**kwargs (Any)`: keyword arguments for the `Task` class</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-core-collections-set-run'><p class="prefect-class">prefect.tasks.core.collections.Set.run</p>(**task_results)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L129">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`**task_results (Any)`: task results to collect into a set</li></ul> **Returns**:     <ul class="args"><li class="args">`set`: a set of task results</li></ul></p>|

---
<br>

 ## Dict
 <div class='class-sig' id='prefect-tasks-core-collections-dict'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.core.collections.Dict</p>(*args, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L140">[source]</a></span></div>

Collects task results into a dict.

**Args**:     <ul class="args"><li class="args">`*args (Any)`: positional arguments for the `Task` class     </li><li class="args">`**kwargs (Any)`: keyword arguments for the `Task` class</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-core-collections-dict-run'><p class="prefect-class">prefect.tasks.core.collections.Dict.run</p>(keys, values)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/core/collections.py#L152">[source]</a></span></div>
<p class="methods">**Args**:     <ul class="args"><li class="args">`keys (Iterable[Any])`: a list of keys that will form the dictionary     </li><li class="args">`values (Iterable[Any])`: a list of values for the dictionary</li></ul> **Returns**:     <ul class="args"><li class="args">`dict`: a dict of task results</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if the number of keys and the number of values are different</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on December 16, 2020 at 21:36 UTC</p>