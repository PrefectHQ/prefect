---
sidebarDepth: 2
editLink: false
---
# Cloud
---
 ## CloudFlowRunner
 <div class='class-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner</p>(flow, state_handlers=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L14">[source]</a></span></div>

FlowRunners handle the execution of Flows and determine the State of a Flow before, during and after the Flow is run.

In particular, through the FlowRunner you can specify which tasks should be the first tasks to run, which tasks should be returned after the Flow is finished, and what states each task should be initialized with.

**Args**:     <ul class="args"><li class="args">`flow (Flow)`: the `Flow` to be run     </li><li class="args">`state_handlers (Iterable[Callable], optional)`: A list of state change handlers         that will be called whenever the flow changes state, providing an         opportunity to inspect or modify the new state. The handler         will be passed the flow runner instance, the old (prior) state, and the new         (current) state, with the following signature:</li></ul>        
```
            state_handler(
                flow_runner: FlowRunner,
                old_state: State,
                new_state: State) -> State

```

If multiple functions are passed, then the `new_state` argument will be the         result of the previous handler.

Note: new FlowRunners are initialized within the call to `Flow.run()` and in general, this is the endpoint through which FlowRunners will be interacted with most frequently.

**Example**: 
```python
@task
def say_hello():
    print('hello')

with Flow("My Flow") as f:
    say_hello()

fr = FlowRunner(flow=f)
flow_state = fr.run()

```

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner-call-runner-target-handlers'><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner.call_runner_target_handlers</p>(old_state, new_state)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L71">[source]</a></span></div>
<p class="methods">A special state handler that the FlowRunner uses to call its flow's state handlers. This method is called as part of the base Runner's `handle_state_change()` method.<br><br>**Args**:     <ul class="args"><li class="args">`old_state (State)`: the old (previous) state     </li><li class="args">`new_state (State)`: the new (current) state</li></ul>**Returns**:     <ul class="args"><li class="args">`State`: the new state</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner-initialize-run'><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner.initialize_run</p>(state, task_states, context, task_contexts, parameters)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L114">[source]</a></span></div>
<p class="methods">Initializes the Task run by initializing state and context appropriately.<br><br>If the provided state is a Submitted state, the state it wraps is extracted.<br><br>**Args**:     <ul class="args"><li class="args">`state (Optional[State])`: the initial state of the run     </li><li class="args">`task_states (Dict[Task, State])`: a dictionary of any initial task states     </li><li class="args">`context (Dict[str, Any], optional)`: prefect.Context to use for execution         to use for each Task run     </li><li class="args">`task_contexts (Dict[Task, Dict[str, Any]], optional)`: contexts that will be provided to each task     </li><li class="args">`parameters(dict)`: the parameter values for the run</li></ul>**Returns**:     <ul class="args"><li class="args">`NamedTuple`: a tuple of initialized objects:         `(state, task_states, context, task_contexts)`</li></ul></p>|

---
<br>

 ## CloudTaskRunner
 <div class='class-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner</p>(task, state_handlers=None, result_handler=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L18">[source]</a></span></div>

TaskRunners handle the execution of Tasks and determine the State of a Task before, during and after the Task is run.

In particular, through the TaskRunner you can specify the states of any upstream dependencies, and what state the Task should be initialized with.

**Args**:     <ul class="args"><li class="args">`task (Task)`: the Task to be run / executed     </li><li class="args">`state_handlers (Iterable[Callable], optional)`: A list of state change handlers         that will be called whenever the task changes state, providing an         opportunity to inspect or modify the new state. The handler         will be passed the task runner instance, the old (prior) state, and the new         (current) state, with the following signature: `state_handler(TaskRunner, old_state, new_state) -> State`;         If multiple functions are passed, then the `new_state` argument will be the         result of the previous handler.     </li><li class="args">`result_handler (ResultHandler, optional)`: the handler to use for         retrieving and storing state results during execution (if the Task doesn't already have one);         if not provided here or by the Task, will default to the one specified in your config</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-call-runner-target-handlers'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.call_runner_target_handlers</p>(old_state, new_state)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L58">[source]</a></span></div>
<p class="methods">A special state handler that the TaskRunner uses to call its task's state handlers. This method is called as part of the base Runner's `handle_state_change()` method.<br><br>**Args**:     <ul class="args"><li class="args">`old_state (State)`: the old (previous) state     </li><li class="args">`new_state (State)`: the new (current) state</li></ul>**Returns**:     <ul class="args"><li class="args">`State`: the new state</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-check-task-is-cached'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.check_task_is_cached</p>(state, inputs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L153">[source]</a></span></div>
<p class="methods">Checks if task is cached in the DB and whether any of the caches are still valid.<br><br>**Args**:     <ul class="args"><li class="args">`state (State)`: the current state of this task     </li><li class="args">`inputs (Dict[str, Result])`: a dictionary of inputs whose keys correspond         to the task's `run()` arguments.</li></ul>**Returns**:     <ul class="args"><li class="args">`State`: the state of the task after running the check</li></ul>**Raises**:     <ul class="args"><li class="args">`ENDRUN`: if the task is not ready to run</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-initialize-run'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.initialize_run</p>(state, context)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L105">[source]</a></span></div>
<p class="methods">Initializes the Task run by initializing state and context appropriately.<br><br>**Args**:     <ul class="args"><li class="args">`state (Optional[State])`: the initial state of the run     </li><li class="args">`context (Dict[str, Any])`: the context to be updated with relevant information</li></ul>**Returns**:     <ul class="args"><li class="args">`tuple`: a tuple of the updated state, context, and upstream_states objects</li></ul></p>|

---
<br>

 ## CloudResultHandler
 <div class='class-sig' id='prefect-engine-cloud-result-handler-cloudresulthandler'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.cloud.result_handler.CloudResultHandler</p>(result_handler_service=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/result_handler.py#L17">[source]</a></span></div>

Hook for storing and retrieving task results from Prefect cloud storage.

**Args**:     <ul class="args"><li class="args">`result_handler_service (str, optional)`: the location of the service         which will further process and store the results; if not provided, will default to         the value of `cloud.result_handler` in your config file</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-cloud-result-handler-cloudresulthandler-read'><p class="prefect-class">prefect.engine.cloud.result_handler.CloudResultHandler.read</p>(uri)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/result_handler.py#L47">[source]</a></span></div>
<p class="methods">Read a result from the given URI location.<br><br>**Args**:     <ul class="args"><li class="args">`uri (str)`: the path to the location of a result</li></ul>**Returns**:     <ul class="args"><li class="args">the deserialized result from the provided URI</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-result-handler-cloudresulthandler-write'><p class="prefect-class">prefect.engine.cloud.result_handler.CloudResultHandler.write</p>(result)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/result_handler.py#L72">[source]</a></span></div>
<p class="methods">Write the provided result to Prefect Cloud.<br><br>**Args**:     <ul class="args"><li class="args">`result (Any)`: the result to store</li></ul>**Returns**:     <ul class="args"><li class="args">`str`: the URI path to the result in Cloud storage</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.3+275.g38ab4505 on May 28, 2019 at 20:38 UTC</p>