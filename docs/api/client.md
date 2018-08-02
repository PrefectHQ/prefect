---
sidebarDepth: 1
---

 ## Client

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.client.Client(api_server=None, graphql_server=None, token=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L15)</span>
Client for the Prefect API.

 ####  ```prefect.client.Client.graphql(query, *variables)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L99)</span>
Convenience function for running queries against the Prefect GraphQL
API

 ####  ```prefect.client.Client.login(email, password, account_slug=None, account_id=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L158)</span>


 ####  ```prefect.client.Client.refresh_token()```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L178)</span>



 ## TaskRuns

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.client.TaskRuns(client, name=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L414)</span>


 ####  ```prefect.client.TaskRuns.get_state(task_run_id)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L418)</span>
Retrieve a flow run's state

 ####  ```prefect.client.TaskRuns.set_state(task_run_id, state, result=None, expected_state=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L440)</span>
Retrieve a task run's state


 ## FlowRuns

### <span style="background-color:rgba(27,31,35,0.05);font-size:0.85em;">class</span> ```prefect.client.FlowRuns(client, name=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L331)</span>


 ####  ```prefect.client.FlowRuns.create(flow_id, parameters=None, parent_taskrun_id=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L369)</span>


 ####  ```prefect.client.FlowRuns.get_state(flow_run_id)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L335)</span>
Retrieve a flow run's state

 ####  ```prefect.client.FlowRuns.run(flow_run_id, start_tasks=None, inputs=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L377)</span>
Queue a flow run to be run

 ####  ```prefect.client.FlowRuns.set_state(flow_run_id, state, result=None, expected_state=None)```<span style="float:right;">[[Source]](https://github.com/PrefectHQ/prefect/tree/master/src/prefect/client.py#L358)</span>
Retrieve a flow run's state


