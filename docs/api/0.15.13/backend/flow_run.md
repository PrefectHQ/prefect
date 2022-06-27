---
sidebarDepth: 2
editLink: false
---
# Flow Run

!!! warning Experimental
    <div class="experimental-warning">
    <svg
        aria-hidden="true"
        focusable="false"
        role="img"
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 448 512"
        >
    <path
    fill="#e90"
    d="M437.2 403.5L320 215V64h8c13.3 0 24-10.7 24-24V24c0-13.3-10.7-24-24-24H120c-13.3 0-24 10.7-24 24v16c0 13.3 10.7 24 24 24h8v151L10.8 403.5C-18.5 450.6 15.3 512 70.9 512h306.2c55.7 0 89.4-61.5 60.1-108.5zM137.9 320l48.2-77.6c3.7-5.2 5.8-11.6 5.8-18.4V64h64v160c0 6.9 2.2 13.2 5.8 18.4l48.2 77.6h-172z"
    >
    </path>
    </svg>

    <div>
    The functionality here is experimental, and may change between versions without notice. Use at your own risk.
    </div>
    </div>
:::

---

 ## FlowRunView
 <div class='class-sig' id='prefect-backend-flow-run-flowrunview'><p class="prefect-sig">class </p><p class="prefect-class">prefect.backend.flow_run.FlowRunView</p>(flow_run_id, name, flow_id, labels, parameters, context, state, states, updated_at, run_config, task_runs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L325">[source]</a></span></div>

A view of Flow Run data stored in the Prefect API.

Provides lazy loading of Task Runs from the flow run.

This object is designed to be an immutable view of the data stored in the Prefect backend API at the time it is created. However, each time a task run is retrieved the latest data for that task will be pulled since they are loaded lazily. Finished task runs will be cached in this object to reduce the amount of network IO.

EXPERIMENTAL: This interface is experimental and subject to change

**Args**:     <ul class="args"><li class="args">`flow_run_id`: The uuid of the flow run     </li><li class="args">`name`: The name of the flow run     </li><li class="args">`flow_id`: The uuid of the flow this run is associated with     </li><li class="args">`state`: The state of the flow run     </li><li class="args">`labels`: The labels assigned to this flow run     </li><li class="args">`parameters`: Parameter overrides for this flow run     </li><li class="args">`context`: Context overrides for this flow run     </li><li class="args">`updated_at`: When this flow run was last updated in the backend     </li><li class="args">`run_config`: The `RunConfig` this flow run was configured with     </li><li class="args">`states`: A sorted list of past states the flow run has been in     </li><li class="args">`task_runs`: An iterable of task run metadata to cache in this view</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-from-flow-run-id'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.from_flow_run_id</p>(flow_run_id, load_static_tasks=False, _cached_task_runs=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L555">[source]</a></span></div>
<p class="methods">Get an instance of this class filled with information by querying for the given flow run id<br><br>**Args**:     <ul class="args"><li class="args">`flow_run_id`: the flow run id to lookup     </li><li class="args">`load_static_tasks`: Pre-populate the task runs with results from flow tasks         that are unmapped.     </li><li class="args">`_cached_task_runs`: Pre-populate the task runs with an existing iterable of         task runs</li></ul> **Returns**:     A populated `FlowRunView` instance</p>|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-get-all-task-runs'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.get_all_task_runs</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L715">[source]</a></span></div>
<p class="methods">Get all task runs for this flow run in a single query. Finished task run data is cached so future lookups do not query the backend.<br><br>**Returns**:     A list of TaskRunView objects</p>|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-get-flow-metadata'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.get_flow_metadata</p>(no_cache=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L490">[source]</a></span></div>
<p class="methods">Flow metadata for the flow associated with this flow run. Retrieved from the API on first call then cached for future calls.<br><br>**Args**:     <ul class="args"><li class="args">`no_cache`: If set, the cached `FlowView` will be ignored and the latest         data for the flow will be pulled.</li></ul> **Returns**:     FlowView: A view of the Flow metadata for the Flow this run is from</p>|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-get-latest'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.get_latest</p>(load_static_tasks=False)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L407">[source]</a></span></div>
<p class="methods">Get the a new copy of this object with the latest data from the API. Cached `TaskRunView` objects will be passed to the new object. Only finished tasks are cached so the cached data cannot be stale.<br><br>This will not mutate the current object.<br><br>**Args**:     <ul class="args"><li class="args">`load_static_tasks`: Pre-populate the task runs with results from flow tasks         that are unmapped. Defaults to `False` because it may be wasteful to         query for task run data when cached tasks are already copied over         from the old object.</li></ul> **Returns**:     A new instance of FlowRunView</p>|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-get-logs'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.get_logs</p>(start_time=None, end_time=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L430">[source]</a></span></div>
<p class="methods">Get logs for this flow run from `start_time` to `end_time`.<br><br>**Args**:     <ul class="args"><li class="args">`start_time (optional)`: A time to start the log query at, useful for         limiting the scope. If not provided, all logs up to `updated_at` are         retrieved.     </li><li class="args">`end_time (optional)`: A time to end the log query at. By default, this is         set to `self.updated_at` which is the last time that the flow run was         updated in the backend before this object was created.</li></ul> **Returns**:     A list of `FlowRunLog` objects sorted by timestamp</p>|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-get-task-run'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.get_task_run</p>(task_slug=None, task_run_id=None, map_index=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L640">[source]</a></span></div>
<p class="methods">Get information about a task run from this flow run. Lookup is available by one of the arguments. If the task information is not available locally already, we will query the database for it. If multiple arguments are provided, we will validate that they are consistent with each other.<br><br>All retrieved task runs that are finished will be cached to avoid re-querying in repeated calls<br><br>**Args**:     <ul class="args"><li class="args">`task_slug`: A task slug string to use for the lookup     </li><li class="args">`task_run_id`: A task run uuid to use for the lookup     </li><li class="args">`map_index`: If given a slug of a mapped task, an index may be provided to         get the the task run for that child task instead of the parent. This         value will only be used for a consistency check if passed with a         `task_run_id`</li></ul> **Returns**:     A cached or newly constructed TaskRunView instance</p>|
 | <div class='method-sig' id='prefect-backend-flow-run-flowrunview-get-task-run-ids'><p class="prefect-class">prefect.backend.flow_run.FlowRunView.get_task_run_ids</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L748">[source]</a></span></div>
<p class="methods">Get all task run ids associated with this flow run. Lazily loaded at call time then cached for future calls.<br><br>**Returns**:     A list of string task run ids</p>|

---
<br>


## Functions
|top-level functions: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-backend-flow-run-watch-flow-run'><p class="prefect-class">prefect.backend.flow_run.watch_flow_run</p>(flow_run_id, stream_states=True, stream_logs=True)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/flow_run.py#L35">[source]</a></span></div>
<p class="methods">Watch execution of a flow run displaying state changes. This function will yield `FlowRunLog` objects until the flow run enters a 'Finished' state.<br><br>If both stream_states and stream_logs are `False` then this will just block until the flow run finishes.<br><br>EXPERIMENTAL: This interface is experimental and subject to change<br><br>**Args**:     <ul class="args"><li class="args">`flow_run_id`: The flow run to watch     </li><li class="args">`stream_states`: If set, flow run state changes will be streamed as logs     </li><li class="args">`stream_logs`: If set, logs will be streamed from the flow run</li></ul> Yields:     FlowRunLog: Sorted log entries</p>|

<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>