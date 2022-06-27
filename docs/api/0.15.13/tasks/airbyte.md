---
sidebarDepth: 2
editLink: false
---
# Airbyte Tasks

!!! tip Verified by Prefect
<div class="verified-task">
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48" fill="none">
<circle cx="24" cy="24" r="24" fill="#42b983"/>
<circle cx="24" cy="24" r="9" stroke="#fff" stroke-width="2"/>
<path d="M19 24L22.4375 27L29 20.5" stroke="#fff" stroke-width="2"/>
</svg>
<div>
    These tasks have been tested and verified by Prefect.
</div>
</div>

---

This module contains a task for triggering [Airbyte](https://airbyte.io/) connection sync jobs
 ## AirbyteConnectionTask
 <div class='class-sig' id='prefect-tasks-airbyte-airbyte-airbyteconnectiontask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.airbyte.airbyte.AirbyteConnectionTask</p>(airbyte_server_host=&quot;localhost&quot;, airbyte_server_port=8000, airbyte_api_version=&quot;v1&quot;, connection_id=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airbyte/airbyte.py#L28">[source]</a></span></div>

Task for triggering Airbyte Connections, where "A connection is a configuration for syncing data between a source and a destination." For more information refer to the [Airbyte docs](https://docs.airbyte.io/understanding-airbyte/connections)

This task assumes that the Airbyte Open-Source, since "For Airbyte Open-Source you don't need the API Token for Authentication! All endpoints are possible to access using the API without it." For more information refer to the [Airbyte docs](https://docs.airbyte.io/api-documentation)

**Args**:     <ul class="args"><li class="args">`airbyte_server_host (str, optional)`: Hostname of Airbyte server where connection is configured.         Defaults to localhost.     </li><li class="args">`airbyte_server_port (str, optional)`: Port that the Airbyte server is listening on.         Defaults to 8000.     </li><li class="args">`airbyte_api_version (str, optional)`: Version of Airbyte API to use to trigger connection sync.         Defaults to v1.     </li><li class="args">`connection_id (str, optional)`: Default connection id to         use for sync jobs, if none is specified to `run`.     </li><li class="args">`**kwargs (Any, optional)`: additional kwargs to pass to the         base Task constructor</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-airbyte-airbyte-airbyteconnectiontask-run'><p class="prefect-class">prefect.tasks.airbyte.airbyte.AirbyteConnectionTask.run</p>(airbyte_server_host=None, airbyte_server_port=None, airbyte_api_version=None, connection_id=None, poll_interval_s=15)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/airbyte/airbyte.py#L191">[source]</a></span></div>
<p class="methods">Task run method for triggering an Airbyte Connection.<br><br>*It is assumed that the user will have previously configured a Source & Destination into a Connection.* e.g. MySql -> CSV<br><br>An invocation of `run` will attempt to start a sync job for the specified `connection_id` representing the Connection in Airbyte.<br><br>`run` will poll Airbyte Server for the Connection status and will only complete when the sync has completed or when it receives an error status code from an API call.<br><br>**Args**:     <ul class="args"><li class="args">`airbyte_server_host (str, optional)`: Hostname of Airbyte server where connection is         configured. Will overwrite the value provided at init if provided.     </li><li class="args">`airbyte_server_port (str, optional)`: Port that the Airbyte server is listening on.         Will overwrite the value provided at init if provided.     </li><li class="args">`airbyte_api_version (str, optional)`: Version of Airbyte API to use to trigger connection         sync. Will overwrite the value provided at init if provided.     </li><li class="args">`connection_id (str, optional)`: if provided,         will overwrite the value provided at init.     </li><li class="args">`poll_interval_s (int, optional)`: this task polls the         Airbyte API for status, if provided this value will         override the default polling time of 15 seconds.</li></ul> **Returns**:     <ul class="args"><li class="args">`dict`: connection_id (str) and succeeded_at (timestamp str)</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on February 23, 2022 at 19:26 UTC</p>