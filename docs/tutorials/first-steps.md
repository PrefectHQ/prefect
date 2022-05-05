---
description: Learn the basics of creating and running Prefect flows and tasks.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - flows
    - subflows
    - async
---

# First steps

If you've never used Prefect before, let's start by exploring the building blocks of a Prefect workflow flows and tasks via an interactive Python session. For these first steps, you can copy and paste the code below into your favorite async-compatible Python REPL.

If you have used Prefect Core and are familiar with Prefect workflows, we still recommend reading through these first steps, particularly [Run a flow within a flow](#run-a-flow-within-a-flow). Orion flows and subflows offer significant new functionality.

## Run a basic flow

A [_flow_](/concepts/flows/) is the basis of Prefect workflows: all workflows are defined within the context of a flow. But it's not complicated: a flow is just a Python function.

The simplest way to begin with Prefect is to import `flow` and annotate your a Python function using the [`@flow` decorator][prefect.flows.flow]:

```python
from prefect import flow

@flow
def my_favorite_function():
    print("This function doesn't do much")
    return 42
```

Running a Prefect workflow manually is as easy as calling the annotated function. In this case, we run the `my_favorite_function()` snippet shown above:

<div class="terminal">
```bash
>>> state = my_favorite_function()
15:27:42.543 | INFO    | prefect.engine - Created flow run 'olive-poodle' for flow 'my-favorite-function'
15:27:42.543 | INFO    | Flow run 'olive-poodle' - Using task runner 'ConcurrentTaskRunner'
This function doesn't do much
15:27:42.652 | INFO    | Flow run 'olive-poodle' - Finished in state Completed(None)
```
</div>

The first thing you'll notice is the messages surrounding the expected output, "This function doesn't do much". 

By adding the `@flow` decorator to your function, function calls will create a _flow run_ &mdash; the Prefect Orion orchestration engine manages task and flow state, including inspecting their progress, regardless of where your flow code runs.

For clarity in future tutorial examples, we may not show these messages in results except where they are relevant to the discussion.

Next, print `state`, which shows the result returned by the `my_favorite_function()` flow.

<div class="terminal">
```bash
>>> print(state)
Completed(None)
```
</div>

!!! note "Flows return states"
    You may notice that this call did not return the number 42 but rather a [Prefect `State` object][prefect.orion.schemas.states.State]. States are the basic currency of communication between Prefect clients and the Prefect API, and can be used to define the conditions for orchestration rules as well as an interface for client-side logic.  

In this case, the state of `my_favorite_function()` is "Completed", with no further message details ("None" in this example).

If you want to see the data returned by the flow, access it via the `.result()` method on the `State` object.

<div class="terminal">
```bash
>>> print(state.result())
42
```
</div>

## Run flows with parameters

As with any Python function, you can pass arguments. The positional and keyword arguments defined on your flow function are called _parameters_. To demonstrate, enter this example in your REPL environment:

```python
import requests
from prefect import flow

@flow
def call_api(url):
    return requests.get(url).json()
```

You can pass any parameters needed by your flow function, and you can pass [parameters on the `@flow`](/api-ref/prefect/flows/#prefect.flows.flow) decorator for configuration as well. We'll cover that in a future tutorial.

For now, run the `call_api()` flow, passing a valid URL as a parameter. In this case, we're sending a POST request to an API that should return valid JSON in the response.

<div class="terminal">
```bash
>>> state = call_api("http://time.jsontest.com/")
14:33:48.770 | INFO    | prefect.engine - Created flow run 'bronze-lyrebird' for flow 'call-api'
14:33:48.770 | INFO    | Flow run 'bronze-lyrebird' - Using task runner 'ConcurrentTaskRunner'
14:33:49.060 | INFO    | Flow run 'bronze-lyrebird' - Finished in state Completed(None)
```
</div>

Again, Prefect Orion automatically orchestrates the flow run. Again, print the state and note the "Completed" state matches what Prefect Orion prints in your terminal.

<div class="terminal">
```bash
>>> print(state)
Completed(None)
```
</div>

As you did previously, print the `result()` to see the JSON returned by the API call:

<div class="terminal">
```bash
>>> print(state.result())
{'date': '02-24-2022', 'milliseconds_since_epoch': 1645731229114, 'time': '07:33:49 PM'}
```
</div>

### Error handling

What happens if the Python function encounters an error while your flow is running? To see what happens whenever our flow does not complete successfully, let's intentionally run the `call_api()` flow above with a bad value for the URL:

<div class="terminal">
```bash
>>> state = call_api("foo")
14:34:35.687 | INFO    | prefect.engine - Created flow run 'purring-swine' for flow 'call-api'
14:34:35.687 | INFO    | Flow run 'purring-swine' - Using task runner 'ConcurrentTaskRunner'
14:34:35.710 | ERROR   | Flow run 'purring-swine' - Encountered exception during execution:
Traceback (most recent call last):
  File "/Users/terry/test/ktest/orion/src/prefect/engine.py", line 445, in orchestrate_flow_run
    result = await run_sync_in_worker_thread(flow_call)
  File "/Users/terry/test/ktest/orion/src/prefect/utilities/asyncio.py", line 51, in run_sync_in_worker_thread
    return await anyio.to_thread.run_sync(context.run, call, cancellable=True)
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/anyio/to_thread.py", line 28, in run_sync
    return await get_asynclib().run_sync_in_worker_thread(func, *args, cancellable=cancellable,
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/anyio/_backends/_asyncio.py", line 818, in run_sync_in_worker_thread
    return await future
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/anyio/_backends/_asyncio.py", line 754, in run
    result = context.run(func, *args)
  File "<stdin>", line 3, in call_api
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/api.py", line 75, in get
    return request('get', url, params=params, **kwargs)
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/api.py", line 61, in request
    return session.request(method=method, url=url, **kwargs)
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/sessions.py", line 515, in request
    prep = self.prepare_request(req)
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/sessions.py", line 443, in prepare_request
    p.prepare(
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/models.py", line 318, in prepare
    self.prepare_url(url, params)
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/models.py", line 392, in prepare_url
    raise MissingSchema(error)
requests.exceptions.MissingSchema: Invalid URL 'foo': No scheme supplied. Perhaps you meant http://foo?
14:34:35.746 | ERROR   | Flow run 'purring-swine' - Finished in state Failed('Flow run encountered an exception.')
```
</div>

In this situation, the call to `requests.get()` encounters an exception, but the flow run still returns! The exception is captured by Orion, which continues to shut down the flow run normally. 

However, in contrast to the 'COMPLETED' state, we now encounter a 'FAILED' state signaling that something unexpected happened during execution.

<div class="terminal">
```bash
>>> print(state)
Failed('Flow run encountered an exception.')
```
</div>

This behavior is consistent across flow runs _and_ task runs and allows you to respond to failures in a first-class way &mdash; whether by configuring orchestration rules in the Orion backend (retry logic) or by directly responding to failed states in client code.

## Run a basic flow with tasks

Let's now add some [_tasks_](/concepts/tasks/) to a flow so that we can orchestrate and monitor at a more granular level. 

A task is a function that represents a distinct piece of work executed within a flow. You don't have to use tasks &mdash; you can include all of the logic of your workflow within the flow itself. However, encapsulating your business logic into smaller task units gives you more granular observability, control over how specific tasks are run (potentially taking advantage of parallel execution), and reusing tasks across flows and subflows.

Creating and adding tasks follows the exact same pattern as for flows. Import `task` and use the [`@task` decorator][prefect.tasks.task] to annotate functions as tasks.

Let's take the previous `call_api()` example and move the actual HTTP request to its own task.

```python
import requests
from prefect import flow, task

@task
def call_api(url):
    response = requests.get(url)
    print(response.status_code)
    return response.json()

@flow
def api_flow(url):
    fact_json = call_api(url)
    return 
```

As you can see, we still call these tasks as normal functions and can pass their return values to other tasks.  We can then
call our flow function &mdash; now called `api_flow()` &mdash; just as before and see the printed output. Prefect manages all the relevant intermediate states.

<div class="terminal">
```bash
>>> state = api_flow("https://catfact.ninja/fact")
15:10:17.955 | INFO    | prefect.engine - Created flow run 'jasper-ammonite' for flow 'api-flow'
15:10:17.955 | INFO    | Flow run 'jasper-ammonite' - Using task runner 'ConcurrentTaskRunner'
15:10:18.022 | INFO    | Flow run 'jasper-ammonite' - Created task run 'call_api-190c7484-0' for task 'call_api'
200
15:10:18.360 | INFO    | Task run 'call_api-190c7484-0' - Finished in state Completed(None)
15:10:18.707 | INFO    | Flow run 'jasper-ammonite' - Finished in state Completed('All states completed.')
```
</div>

And of course we can create tasks that take input from and pass input to other tasks.

```python
import requests
from prefect import flow, task

@task
def call_api(url):
    response = requests.get(url)
    print(response.status_code)
    return response.json()

@task
def parse_fact(response):
    print(response["fact"])
    return 

@flow
def api_flow(url):
    fact_json = call_api(url)
    parse_fact(fact_json)
    return 
```

You should end up printing out an interesting fact:

<div class="terminal">
```bash
>>> state = api_flow("https://catfact.ninja/fact")
15:12:40.847 | INFO    | prefect.engine - Created flow run 'funny-guillemot' for flow 'api-flow'
15:12:40.847 | INFO    | Flow run 'funny-guillemot' - Using task runner 'ConcurrentTaskRunner'
15:12:40.912 | INFO    | Flow run 'funny-guillemot' - Created task run 'call_api-190c7484-0' for task 'call_api'
15:12:40.968 | INFO    | Flow run 'funny-guillemot' - Created task run 'parse_fact-b0346046-0' for task 'parse_fact'
200
15:12:41.402 | INFO    | Task run 'call_api-190c7484-0' - Finished in state Completed(None)
Abraham Lincoln loved cats. He had four of them while he lived in the White House.
15:12:41.676 | INFO    | Task run 'parse_fact-b0346046-0' - Finished in state Completed(None)
15:12:42.057 | INFO    | Flow run 'funny-guillemot' - Finished in state Completed('All states completed.')
```
</div>

!!! note "Combining tasks with arbitrary Python code"
    Notice in the above example that *all* of our Python logic is encapsulated within task functions. While there are many benefits to using Prefect in this way, it is not a strict requirement.  Interacting with the results of your Prefect tasks requires an understanding of [Prefect futures](/api-ref/prefect/futures/).

## Run a flow within a flow

Not only can you call tasks functions within a flow, but you can also call other flow functions! Flows that run within other flows are called [_subflows_](/concepts/flows/#subflows) and allow you to efficiently manage, track, and version common multi-task logic.  

Consider the following simple example:

```python
from prefect import flow

@flow
def common_flow(config: dict):
    print("I am a subgraph that shows up in lots of places!")
    intermediate_result = 42
    return intermediate_result

@flow
def main_flow():
    # do some things
    # then call another flow function
    data = common_flow(config={})
    # do more things
```

Whenever we run `main_flow` as above, a new run will be generated for `common_flow` as well.  Not only is this run tracked as a subflow run of `main_flow`, but you can also inspect it independently in the UI!

<div class="terminal">
```bash
>>> flow_state = main_flow()
15:16:18.344 | INFO    | prefect.engine - Created flow run 'teal-goose' for flow 'main-flow'
15:16:18.345 | INFO    | Flow run 'teal-goose' - Using task runner 'ConcurrentTaskRunner'
15:16:18.583 | INFO    | Flow run 'teal-goose' - Created subflow run 'brawny-falcon' for flow 'common-flow'
I am a subgraph that shows up in lots of places!
15:16:18.805 | INFO    | Flow run 'brawny-falcon' - Finished in state Completed(None)
15:16:18.933 | INFO    | Flow run 'teal-goose' - Finished in state Completed('All states completed.')
```
</div>

You can confirm this for yourself by spinning up the UI using the `prefect orion start` CLI command from your terminal:

<div class="terminal">
```bash
$ prefect orion start
```
</div>

Open the URL for the Orion UI ([http://127.0.0.1:4200](http://127.0.0.1:4200) by default) in a browser. You should see all of the runs that we have run throughout this tutorial, including one for `common_flow`:

![Viewing the orchestrated flow runs in the Orion UI.](/img/tutorials/first-steps-ui.png)

## Asynchronous functions

Even asynchronous functions work with Prefect!  Here's a variation of the previous examples that makes the API request as an async operation:

```python
import requests
import asyncio
from prefect import flow, task

@task
async def call_api(url):
    response = requests.get(url)
    print(response.status_code)
    return response.json()

@flow
async def async_flow(url):
    fact_json = await call_api(url)
    return 
```

If we run this in the REPL, the output looks just like previous runs.

<div class="terminal">
```bash
>>> asyncio.run(async_flow("https://catfact.ninja/fact"))
16:41:50.298 | INFO    | prefect.engine - Created flow run 'dashing-elephant' for flow 'async-flow'
16:41:50.298 | INFO    | Flow run 'dashing-elephant' - Using task runner 'ConcurrentTaskRunner'
16:41:50.352 | INFO    | Flow run 'dashing-elephant' - Created task run 'call_api-190c7484-0' for task 'call_api'
200
16:41:50.582 | INFO    | Task run 'call_api-190c7484-0' - Finished in state Completed(None)
16:41:50.890 | INFO    | Flow run 'dashing-elephant' - Finished in state Completed('All states completed.')
Completed(message='All states completed.', type=COMPLETED, result=[Completed(message=None, type=COMPLETED, 
result={'fact': 'Cats have about 130,000 hairs per square inch (20,155 hairs per square centimeter).', 'length': 83}, 
task_run_id=1a50b4df-a505-4a2f-8d28-3d1bf7db206e)], flow_run_id=42d2bd19-8c3b-4dd1-b494-52cc764acc3d)
```
</div>

This is a more advanced use case and will be covered in future tutorials.

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Flows](/concepts/flows/)
    - [Tasks](/concepts/tasks/)
    - [States](/concepts/states/)
