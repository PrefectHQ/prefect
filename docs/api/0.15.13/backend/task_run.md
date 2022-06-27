---
sidebarDepth: 2
editLink: false
---
# Task Run

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

 ## TaskRunView
 <div class='class-sig' id='prefect-backend-task-run-taskrunview'><p class="prefect-sig">class </p><p class="prefect-class">prefect.backend.task_run.TaskRunView</p>(task_run_id, task_id, task_slug, name, state, map_index, flow_run_id)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/task_run.py#L15">[source]</a></span></div>

A view of Task Run data stored in the Prefect API.

Provides lazy loading of task run return values from Prefect `Result` locations.

This object is designed to be an immutable view of the data stored in the Prefect backend API at the time it is created.

EXPERIMENTAL: This interface is experimental and subject to change

**Args**:     <ul class="args"><li class="args">`task_run_id`: The task run uuid     </li><li class="args">`task_id`: The uuid of the task associated with this task run     </li><li class="args">`task_slug`: The slug of the task associated with this task run     </li><li class="args">`name`: The task run name     </li><li class="args">`state`: The state of the task run     </li><li class="args">`map_index`: The map index of the task run. Is -1 if it is not a mapped subtask,          otherwise it is in the index of the task run in the mapping     </li><li class="args">`flow_run_id`: The uuid of the flow run associated with this task run</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-backend-task-run-taskrunview-from-task-run-id'><p class="prefect-class">prefect.backend.task_run.TaskRunView.from_task_run_id</p>(task_run_id=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/task_run.py#L244">[source]</a></span></div>
<p class="methods">Get an instance of this class; query by task run id<br><br>**Args**:     <ul class="args"><li class="args">`task_run_id`: The UUID identifying the task run in the backend</li></ul> **Returns**:     A populated `TaskRunView` instance</p>|
 | <div class='method-sig' id='prefect-backend-task-run-taskrunview-from-task-slug'><p class="prefect-class">prefect.backend.task_run.TaskRunView.from_task_slug</p>(task_slug, flow_run_id, map_index=-1)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/task_run.py#L265">[source]</a></span></div>
<p class="methods">Get an instance of this class; query by task slug and flow run id.<br><br>**Args**:     <ul class="args"><li class="args">`task_slug`: The unique string identifying this task in the flow. Typically         `<task-name>-1`.     </li><li class="args">`flow_run_id`: The UUID identifying the flow run the task run occurred in     </li><li class="args">`map_index (optional)`: The index to access for mapped tasks; defaults to         the parent task with a map index of -1</li></ul> **Returns**:     A populated `TaskRunView` instance</p>|
 | <div class='method-sig' id='prefect-backend-task-run-taskrunview-get-result'><p class="prefect-class">prefect.backend.task_run.TaskRunView.get_result</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/task_run.py#L58">[source]</a></span></div>
<p class="methods">The result of this task run loaded from the `Result` location. Lazily loaded on the first call then cached for repeated access. For the parent of mapped task runs, this will include the results of all children. May require credentials to be present if the result location is remote (ie S3). If your flow was run on another machine and `LocalResult` was used, we will fail to load the result.<br><br>See `TaskRunView.iter_mapped` for lazily iterating through mapped tasks instead of retrieving all of the results at once.<br><br>**Returns**:     Any: The value your task returned</p>|
 | <div class='method-sig' id='prefect-backend-task-run-taskrunview-iter-mapped'><p class="prefect-class">prefect.backend.task_run.TaskRunView.iter_mapped</p>()<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/backend/task_run.py#L183">[source]</a></span></div>
<p class="methods">Iterate over the results of a mapped task, yielding a `TaskRunView` for each map index. This query is not performed in bulk so the results can be lazily consumed. If you want all of the task results at once, use `result` instead.<br><br>Yields:     A `TaskRunView` for each mapped item</p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>