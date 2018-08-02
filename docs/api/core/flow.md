---
sidebarDepth: 1
---

 ## Flow

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.core.flow.Flow(name=None, version=None, schedule=None, description=None, environment=None, tasks=None, edges=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L42)</span>
A class that automatically uses a specified JSONCodec to serialize itself.

 ####  ```prefect.core.flow.Flow.add_edge(upstream_task, downstream_task, key=None, validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L185)</span>


 ####  ```prefect.core.flow.Flow.add_task(task)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L169)</span>


 ####  ```prefect.core.flow.Flow.all_downstream_edges()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L249)</span>


 ####  ```prefect.core.flow.Flow.all_upstream_edges()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L243)</span>


 ####  ```prefect.core.flow.Flow.copy()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L96)</span>


 ####  ```prefect.core.flow.Flow.downstream_tasks(task)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L272)</span>


 ####  ```prefect.core.flow.Flow.edges_from(task)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L262)</span>


 ####  ```prefect.core.flow.Flow.edges_to(task)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L255)</span>


 ####  ```prefect.core.flow.Flow.generate_flow_id()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L470)</span>
Flows are identified by their name and version.

 ####  ```prefect.core.flow.Flow.generate_task_ids()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L477)</span>


 ####  ```prefect.core.flow.Flow.parameters(only_required=False)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L132)</span>
Returns details about any Parameters of this flow

 ####  ```prefect.core.flow.Flow.restore_graph_on_error(validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L144)</span>
A context manager that saves the Flow's graph (tasks & edges) and
restores it if an error is raised. It can be used to test potentially
erroneous configurations (for example, ones that might include cycles)
without modifying the graph.

It will automatically check for cycles when restored.

```python
with flow.restore_graph_on_error():
    # this will raise an error, but the flow graph will not be modified
    add_cycle_to_graph(flow)
```

 ####  ```prefect.core.flow.Flow.root_tasks()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L118)</span>
Returns the root tasks of the Flow -- tasks that have no upstream
dependencies.

 ####  ```prefect.core.flow.Flow.run(parameters=None, return_tasks=None, *kwargs)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L388)</span>
Run the flow.

 ####  ```prefect.core.flow.Flow.serialize()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L431)</span>


 ####  ```prefect.core.flow.Flow.set_dependencies(task, upstream_tasks=None, downstream_tasks=None, keyword_tasks=None, validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L330)</span>
Convenience function for adding task dependencies on upstream tasks.

**Args**:


task (Object): a Task that will become part of the Flow. If the task is not a
Task subclass, Prefect will attempt to convert it to one.

upstream_tasks ([object]): Tasks that will run before the task runs. If any task
is not a Task subclass, Prefect will attempt to convert it to one.

downstream_tasks ([object]): Tasks that will run after the task runs. If any task
is not a Task subclass, Prefect will attempt to convert it to one.

keyword_tasks ({key: object}): The results of these tasks
will be provided to the task under the specified keyword
arguments. If any task is not a Task subclass, Prefect will attempt to
convert it to one.

 ####  ```prefect.core.flow.Flow.sorted_tasks(root_tasks=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L281)</span>


 ####  ```prefect.core.flow.Flow.terminal_tasks()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L125)</span>
Returns the terminal tasks of the Flow -- tasks that have no downstream
dependencies.

 ####  ```prefect.core.flow.Flow.update(flow, validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L227)</span>


 ####  ```prefect.core.flow.Flow.upstream_tasks(task)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L269)</span>


 ####  ```prefect.core.flow.Flow.validate()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L275)</span>
Checks the flow for cycles and raises an error if one is found.

 ####  ```prefect.core.flow.Flow.visualize()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L456)</span>



