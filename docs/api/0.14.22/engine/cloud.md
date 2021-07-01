---
sidebarDepth: 2
editLink: false
---
# Cloud
---
 ## CloudFlowRunner
 <div class='class-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner</p>(flow, state_handlers=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L22">[source]</a></span></div>

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
 | <div class='method-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner-call-runner-target-handlers'><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner.call_runner_target_handlers</p>(old_state, new_state)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L104">[source]</a></span></div>
<p class="methods">A special state handler that the FlowRunner uses to call its flow's state handlers. This method is called as part of the base Runner's `handle_state_change()` method.<br><br>**Args**:     <ul class="args"><li class="args">`old_state (State)`: the old (previous) state     </li><li class="args">`new_state (State)`: the new (current) state</li></ul> **Returns**:     <ul class="args"><li class="args">`State`: the new state</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner-check-for-cancellation'><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner.check_for_cancellation</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L168">[source]</a></span></div>
<p class="methods">Contextmanager used to wrap a cancellable section of a flow run.</p>|
 | <div class='method-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner-initialize-run'><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner.initialize_run</p>(state, task_states, context, task_contexts, parameters)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L339">[source]</a></span></div>
<p class="methods">Initializes the Task run by initializing state and context appropriately.<br><br>If the provided state is a Submitted state, the state it wraps is extracted.<br><br>**Args**:     <ul class="args"><li class="args">`state (Optional[State])`: the initial state of the run     </li><li class="args">`task_states (Dict[Task, State])`: a dictionary of any initial task states     </li><li class="args">`context (Dict[str, Any], optional)`: prefect.Context to use for execution         to use for each Task run     </li><li class="args">`task_contexts (Dict[Task, Dict[str, Any]], optional)`: contexts that will be         provided to each task     </li><li class="args">`parameters(dict)`: the parameter values for the run</li></ul> **Returns**:     <ul class="args"><li class="args">`NamedTuple`: a tuple of initialized objects:         `(state, task_states, context, task_contexts)`</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-flow-runner-cloudflowrunner-run'><p class="prefect-class">prefect.engine.cloud.flow_runner.CloudFlowRunner.run</p>(state=None, task_states=None, return_tasks=None, parameters=None, task_runner_state_handlers=None, executor=None, context=None, task_contexts=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/flow_runner.py#L239">[source]</a></span></div>
<p class="methods">The main endpoint for FlowRunners.  Calling this method will perform all computations contained within the Flow and return the final state of the Flow.<br><br>**Args**:     <ul class="args"><li class="args">`state (State, optional)`: starting state for the Flow. Defaults to         `Pending`     </li><li class="args">`task_states (dict, optional)`: dictionary of task states to begin         computation with, with keys being Tasks and values their corresponding state     </li><li class="args">`return_tasks ([Task], optional)`: list of Tasks to include in the         final returned Flow state. Defaults to `None`     </li><li class="args">`parameters (dict, optional)`: dictionary of any needed Parameter         values, with keys being strings representing Parameter names and values being         their corresponding values     </li><li class="args">`task_runner_state_handlers (Iterable[Callable], optional)`: A list of state change         handlers that will be provided to the task_runner, and called whenever a task         changes state.     </li><li class="args">`executor (Executor, optional)`: executor to use when performing         computation; defaults to the executor specified in your prefect configuration     </li><li class="args">`context (Dict[str, Any], optional)`: prefect.Context to use for execution         to use for each Task run     </li><li class="args">`task_contexts (Dict[Task, Dict[str, Any]], optional)`: contexts that will be         provided to each task</li></ul> **Returns**:     <ul class="args"><li class="args">`State`: `State` representing the final post-run state of the `Flow`.</li></ul></p>|

---
<br>

 ## CloudTaskRunner
 <div class='class-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner'><p class="prefect-sig">class </p><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner</p>(task, state_handlers=None, flow_result=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L18">[source]</a></span></div>

TaskRunners handle the execution of Tasks and determine the State of a Task before, during and after the Task is run.

In particular, through the TaskRunner you can specify the states of any upstream dependencies, and what state the Task should be initialized with.

**Args**:     <ul class="args"><li class="args">`task (Task)`: the Task to be run / executed     </li><li class="args">`state_handlers (Iterable[Callable], optional)`: A list of state change handlers         that will be called whenever the task changes state, providing an opportunity to         inspect or modify the new state. The handler will be passed the task runner         instance, the old (prior) state, and the new (current) state, with the following         signature: `state_handler(TaskRunner, old_state, new_state) -> State`; If multiple         functions are passed, then the `new_state` argument will be the result of the         previous handler.     </li><li class="args">`flow_result`: the result instance configured for the flow (if any)</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-call-runner-target-handlers'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.call_runner_target_handlers</p>(old_state, new_state)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L49">[source]</a></span></div>
<p class="methods">A special state handler that the TaskRunner uses to call its task's state handlers. This method is called as part of the base Runner's `handle_state_change()` method.<br><br>**Args**:     <ul class="args"><li class="args">`old_state (State)`: the old (previous) state     </li><li class="args">`new_state (State)`: the new (current) state</li></ul> **Returns**:     <ul class="args"><li class="args">`State`: the new state</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-check-task-is-cached'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.check_task_is_cached</p>(state, inputs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L183">[source]</a></span></div>
<p class="methods">Checks if task is cached in the DB and whether any of the caches are still valid.<br><br>**Args**:     <ul class="args"><li class="args">`state (State)`: the current state of this task     </li><li class="args">`inputs (Dict[str, Result])`: a dictionary of inputs whose keys correspond         to the task's `run()` arguments.</li></ul> **Returns**:     <ul class="args"><li class="args">`State`: the state of the task after running the check</li></ul> **Raises**:     <ul class="args"><li class="args">`ENDRUN`: if the task is not ready to run</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-initialize-run'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.initialize_run</p>(state, context)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L138">[source]</a></span></div>
<p class="methods">Initializes the Task run by initializing state and context appropriately.<br><br>**Args**:     <ul class="args"><li class="args">`state (Optional[State])`: the initial state of the run     </li><li class="args">`context (Dict[str, Any])`: the context to be updated with relevant information</li></ul> **Returns**:     <ul class="args"><li class="args">`tuple`: a tuple of the updated state, context, and upstream_states objects</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-load-results'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.load_results</p>(state, upstream_states)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L259">[source]</a></span></div>
<p class="methods">Given the task's current state and upstream states, populates all relevant result objects for this task run.<br><br>**Args**:     <ul class="args"><li class="args">`state (State)`: the task's current state.     </li><li class="args">`upstream_states (Dict[Edge, State])`: the upstream state_handlers</li></ul> **Returns**:     <ul class="args"><li class="args">`Tuple[State, dict]`: a tuple of (state, upstream_states)</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-run'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.run</p>(state=None, upstream_states=None, context=None, is_mapped_parent=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L325">[source]</a></span></div>
<p class="methods">The main endpoint for TaskRunners.  Calling this method will conditionally execute `self.task.run` with any provided inputs, assuming the upstream dependencies are in a state which allow this Task to run.  Additionally, this method will wait and perform Task retries which are scheduled for <= 1 minute in the future.<br><br>**Args**:     <ul class="args"><li class="args">`state (State, optional)`: initial `State` to begin task run from;         defaults to `Pending()`     </li><li class="args">`upstream_states (Dict[Edge, State])`: a dictionary         representing the states of any tasks upstream of this one. The keys of the         dictionary should correspond to the edges leading to the task.     </li><li class="args">`context (dict, optional)`: prefect Context to use for execution     </li><li class="args">`is_mapped_parent (bool)`: a boolean indicating whether this task run is the run of         a parent mapped task</li></ul> **Returns**:     <ul class="args"><li class="args">`State` object representing the final post-run state of the Task</li></ul></p>|
 | <div class='method-sig' id='prefect-engine-cloud-task-runner-cloudtaskrunner-set-task-run-name'><p class="prefect-class">prefect.engine.cloud.task_runner.CloudTaskRunner.set_task_run_name</p>(task_inputs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/cloud/task_runner.py#L298">[source]</a></span></div>
<p class="methods">Sets the name for this task run by calling the `set_task_run_name` mutation.<br><br>**Args**:     <ul class="args"><li class="args">`task_inputs (Dict[str, Result])`: a dictionary of inputs whose keys correspond         to the task's `run()` arguments.</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>