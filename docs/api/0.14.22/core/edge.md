---
sidebarDepth: 2
editLink: false
---
# Edge
---
 ## Edge
 <div class='class-sig' id='prefect-core-edge-edge'><p class="prefect-sig">class </p><p class="prefect-class">prefect.core.edge.Edge</p>(upstream_task, downstream_task, key=None, mapped=None, flattened=None, flow=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/core/edge.py#L35">[source]</a></span></div>

Edges represent connections between Tasks.

At a minimum, an edge links an `upstream_task` and a `downstream_task` indicating that the downstream task shouldn't attempt to run until the upstream task is complete.

In addition, edges can specify a key that describe how upstream results are passed to the downstream task.

**Args**:     <ul class="args"><li class="args">`upstream_task (Any)`: the task that must run before the         `downstream_task`. It will be converted to as task with         `prefect.utilities.tasks.as_task()`     </li><li class="args">`downstream_task (Any)`: the task that will be run after the         `upstream_task`. The upstream task state is passed to the         downstream task's trigger function to determine whether the         downstream task should run. It will be converted to as task with         `prefect.utilities.tasks.as_task()`     </li><li class="args">`key (str, optional)`: Passing a key indicates         that the upstream result should be passed to the downstream         task as a keyword argument given by `key`.     </li><li class="args">`mapped (bool, optional)`: boolean indicating whether this edge         represents a downstream mapped task; defaults to `False`     </li><li class="args">`flattened (bool, optional)`: boolean indicating whether this edge         represents an upstream flattened task; defaults to `False     </li><li class="args">`flow (prefect.Flow, optional)`: a flow object that will be used         if either the `upstream_task` or `downstream_task` is a         collection that needs to be bound to a flow. If not provided,         the context flow will be used instead.</li></ul> The key indicates that the result of the upstream task should be passed to the downstream task under the key.

In general, Edges are created and handled in the background by the [Flow](flow.html) class and will not be directly instantiated by users.

**Example**:     
```python
    from prefect import *
    from prefect.core import Edge

    class Add(Task):
        def run(self, x):
            return x + 1

    class Number(Task):
        def run(self):
            return 2

    # passes the result of the Number() task to Add() as 'x'
    edge = Edge(Number(), Add(), key='x')

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-core-edge-edge-serialize'><p class="prefect-class">prefect.core.edge.Edge.serialize</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/core/edge.py#L153">[source]</a></span></div>
<p class="methods">Represents the Edge as a dict.</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>