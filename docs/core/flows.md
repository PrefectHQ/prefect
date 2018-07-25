 # _class_ **```prefect.core.flow.Flow```**```(name=None, version=None, schedule=None, description=None, environment=None, tasks=None, edges=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L51)</span>
A class that automatically uses a specified JSONCodec to serialize itself.

 ##  **```prefect.core.flow.Flow.add_edge```**```(upstream_task, downstream_taskkey=None, validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L195)</span>


 ##  **```prefect.core.flow.Flow.add_task```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L181)</span>


 ##  **```prefect.core.flow.Flow.all_downstream_edges```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L258)</span>


 ##  **```prefect.core.flow.Flow.all_upstream_edges```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L251)</span>


 ##  **```prefect.core.flow.Flow.copy```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L106)</span>


 ##  **```prefect.core.flow.Flow.downstream_tasks```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L282)</span>


 ##  **```prefect.core.flow.Flow.edges_from```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L272)</span>


 ##  **```prefect.core.flow.Flow.edges_to```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L265)</span>


 ##  **```prefect.core.flow.Flow.generate_flow_id```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L467)</span>
Flows are identified by their name and version.

 ##  **```prefect.core.flow.Flow.generate_task_ids```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L474)</span>


 ##  **```prefect.core.flow.Flow.parameters```**```(only_required=False)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L144)</span>
Returns details about any Parameters of this flow

 ##  **```prefect.core.flow.Flow.restore_graph_on_error```**```(validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L156)</span>
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

 ##  **```prefect.core.flow.Flow.root_tasks```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L128)</span>
Returns the root tasks of the Flow -- tasks that have no upstream
dependencies.

 ##  **```prefect.core.flow.Flow.run```**```(parameters=None, return_tasks=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L399)</span>
Run the flow.

 ##  **```prefect.core.flow.Flow.serialize```**```(seed=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L428)</span>


 ##  **```prefect.core.flow.Flow.set_dependencies```**```(taskupstream_tasks=None, downstream_tasks=None, keyword_tasks=None, validate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L341)</span>
Convenience function for adding task dependencies on upstream tasks.

Args:
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

 ##  **```prefect.core.flow.Flow.sorted_tasks```**```(root_tasks=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L291)</span>


 ##  **```prefect.core.flow.Flow.terminal_tasks```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L136)</span>
Returns the terminal tasks of the Flow -- tasks that have no downstream
dependencies.

 ##  **```prefect.core.flow.Flow.update```**```(flowvalidate=True)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L235)</span>


 ##  **```prefect.core.flow.Flow.upstream_tasks```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L279)</span>


 ##  **```prefect.core.flow.Flow.validate```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L285)</span>
Checks the flow for cycles and raises an error if one is found.

 ##  **```prefect.core.flow.Flow.visualize```**```()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/core/flow.py#L453)</span>



