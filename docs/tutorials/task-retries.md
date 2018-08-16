---
sidebarDepth: 0
---

## Task Retries

<img src='/retry_success.png'>

When designing data workflows, it is to be expected that certain components might occasionally fail or need manual intervention.  In these situations, to avoid re-running entire Flows from scratch and still ensure the necessary data arrives at the paused / retrying Task, Prefect will automatically detect that caching is required and will store the necessary inputs to be used in subsequent Flow runs.

There are many reasons a given Flow run might result in a Task failure; for example, if a Task pings an external service that is temporarily down, or queries a database that is currently locked, that Task cannot proceed.  

Of course, you could encapsulate your own error-handling logic in the task itself with `try / except` clauses, etc. However, allowing Prefect to register the Task failure provides many benefits:
- provides you with out-of-the-box logging for the failure
- you write the code that you _want_ run and let Prefect handle the rest; there's no need to write excessively [defensive code](https://en.wikipedia.org/wiki/Defensive_programming).  This keeps your code clean and readable with clear intent.
- allows you to easily handle complicated state-based logic; for example, if a task fails and you want to execute a plan B, you can create another task with the appropriate triggers that will only run upon failure of its dependency.  After a successful run, you can inspect the Flow to see that the first attempt failed, and plan B succeeded. If all that logic was contained within a single task, this would not be as easy to inspect.

Let's dig into this further with an example.

::: tip Example
We have two tasks: `create_payload` and `ping_external_service` which depend on each other.  We imagine `create_payloud` performs expensive computation, and its result is used by `ping_external_service` to ping an external service (which may occasionally go down).  Ideally we don't want to rerun `create_payload` if the external service is temporarily unavailable.
:::

In Prefect, we can set a retry limit (using the keyword `max_retries`) on tasks we expect could fail; behind the scenes, Prefect will store all  inputs / parameters required to execute the retrying Task, so that on the next run any previously Successful tasks aren't unnecessarily rerun.

To create the Tasks, we use the `@task` decorator, which optionally accepts `kwargs` related to the behavior of the Task.


```python
import prefect
from prefect import task, Flow

import requests
from unittest.mock import MagicMock, patch
from time import sleep


@task
def create_payload():
    "Performs expensive computation to create / return an URL"
    
    sleep(5) # for whatever reason, getting to this point takes a long time
    return 'http://www.google.com'


@task(max_retries=1)
def ping_external_service(url):
    "Performs a simple GET request to the provided URL, and returns the text of the response."
    
    if prefect.context.get("_fail"):
        raise ValueError(f"Request failed with status code 418.")
    else:
        r = requests.get(url)
        return r.text
```

To combine the Tasks into a Flow and specify the appropriate dependencies, we use the Flow class as a `contextmanager` with the optional `name` keyword and proceed to simply call the Tasks as functions in the natural way.  Note that no computation will be executed until we call the Flow's `run` method.


```python
with Flow(name="retry example") as f:
    text = ping_external_service(create_payload())
```

Now that we have created our Flow `f`, we could continue to add Tasks and dependencies to it through a variety of methods such as `add_task` and `set_dependencies`, or inspect its current state with methods such as `visualize` and `terminal_tasks`.

To actually perform the computation, we call `f.run()` and specify which tasks we want returned for inspection.  For the first run, we ensure that the request fails using the `prefect.context` (see the docs for more information on context).


```python
%%time
with prefect.context(_fail=True):
    flow_state = f.run(return_tasks=f.tasks)

##    CPU times: user 5.65 ms, sys: 1.46 ms, total: 7.12 ms
##    Wall time: 5.01 s
```

As expected, the Flow run took 5 seconds due to the `create_payload` task.  We can now inspect both the state of the Flow as well as the state of the requested `return_tasks`.


```python
print(f"Flow state: {flow_state}\n")
print(f"Flow results: {flow_state.result}")

## Flow state: Pending("Some terminal tasks are still pending.")
    
## Flow results: {
##      <Task: create_payload>: Success("Task run succeeded."), 
##      <Task: ping_external_service>: Retrying("Retrying Task (after attempt 1 of 2)")
##                }
```

No surprises here; the entire Flow is `Pending` because its sole terminal task (`ping_external_service`) hasn't finished yet.  

<img src='/retry.png'>

To trigger a retry / rerun, we need to run `f.run()` again, providing the Retrying Task State, and explicitly telling the flow which task to start with.  Contained within the `Retrying` state are the necessary cached inputs that were provided to `ping_external_service` on the last run.

When we rerun this Flow, we expect it to take significantly less time and return a successful result.

::: tip NOTE:
Providing states to the `run` method will be handled by the server on the actual `Prefect` platform.
:::

```python
%%time
new_flow_state = f.run(return_tasks=[text], 
                       task_states={text: flow_state.result[text]},
                       start_tasks=[text])

##    CPU times: user 15.5 ms, sys: 5.91 ms, total: 21.4 ms
##    Wall time: 167 ms
```


```python
print(f"Flow state: {new_flow_state}\n")
print(f"Flow results: {new_flow_state.result}")

##     Flow state: Success("All key tasks succeeded.")
    
##     Flow results: {<Task: ping_external_service>: Success("Task run succeeded.")}
```
