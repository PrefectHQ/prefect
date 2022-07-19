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

If you've never used Prefect before, let's start by exploring the core elements of Prefect workflows: flows and tasks.

If you have used Prefect 1.0 ("Prefect Core") and are familiar with Prefect workflows, we still recommend reading through these first steps, particularly [Run a flow within a flow](#run-a-flow-within-a-flow). Prefect 2.0 flows and subflows offer significant new functionality.

## Prerequisites

These tutorials assume you have [installed Prefect](/getting-started/installation/). 

If you have at least basic Python programming experience, the examples in these tutorials should be easy to follow. 

To show the basics of Prefect flows and tasks, the examples begin by using an interactive Python interpreter (REPL) session. An easy way to start the interpreter is by simply opening a terminal or console where Python is installed and running the `python` command. You should see something like this.

<div class="terminal">
```bash
$ python
Python 3.9.10 (main, Apr  1 2022, 11:58:52) 
[Clang 13.0.0 (clang-1300.0.29.30)] on darwin
Type "help", "copyright", "credits" or "license" for more information.
>>>
```
</div>

If you prefer working with iPython, Jupyter Notebooks, or script files, most of the examples are easily adapted to those environments.

## Flows, tasks, and subflows

Let's start with the basics, defining the central components of Prefect workflows.

A [flow](/concepts/flows/) is the basis of all Prefect workflows. A flow is a Python function decorated with a `@flow` decorator. 

A [task](/concepts/tasks/) is a Python function decorated with a `@task` decorator. Tasks represents distinct pieces of work executed within a flow. 

All Prefect workflows are defined within the context of a flow. Every Prefect workflow must contain at least one flow function that serves as the entrypoint for execution of the flow. 

Flows can include calls to tasks as well as to child flows, which we call "subflows" in this context. At a high level, this is just like writing any other Python applications: you organize specific, repetitive work into tasks, and call those tasks from flows.

## Run a basic flow

The simplest way to begin with Prefect is to import `flow` and annotate your Python function using the [`@flow`][prefect.flows.flow]  decorator:

```python
from prefect import flow

@flow
def my_favorite_function():
    print("This function doesn't do much")
    return 42
```

Running a Prefect flow manually is as easy as calling the annotated function &mdash; in this case, the `my_favorite_function()` snippet shown above:

<div class="terminal">
```bash
from prefect import flow

>>> @flow
... def my_favorite_function():
...     print("This function doesn't do much")
...     return 42
...
>>> number = my_favorite_function()
15:27:42.543 | INFO    | prefect.engine - Created flow run 'olive-poodle' for flow 'my-favorite-function'
15:27:42.543 | INFO    | Flow run 'olive-poodle' - Using task runner 'ConcurrentTaskRunner'
This function doesn't do much
15:27:42.652 | INFO    | Flow run 'olive-poodle' - Finished in state Completed(None)
```
</div>

Notice the messages surrounding the expected output, "This function doesn't do much". 

By adding the `@flow` decorator to a function, function calls will create a _flow run_ &mdash; the Prefect Orion orchestration engine manages flow and task state, including inspecting their progress, regardless of where your flow code runs.

For clarity in future tutorial examples, these Prefect orchestration messages in results will only be shown where they are relevant to the discussion.


In this case, the state of `my_favorite_function()` is "Completed", with no further message details. This reflects the logged message we saw earlier, `Flow run 'olive-poodle' - Finished in state Completed()`. 

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
>>> import requests
>>> from prefect import flow
>>>
>>> @flow
... def call_api(url):
...     return requests.get(url).json()
...
>>> api_result = call_api("http://time.jsontest.com/")
14:33:48.770 | INFO    | prefect.engine - Created flow run 'bronze-lyrebird' for flow 'call-api'
14:33:48.770 | INFO    | Flow run 'bronze-lyrebird' - Using task runner 'ConcurrentTaskRunner'
14:33:49.060 | INFO    | Flow run 'bronze-lyrebird' - Finished in state Completed()
```
</div>

Again, Prefect Orion automatically orchestrates the flow run.

As you did previously, print you can print the JSON returned by the API call:

<div class="terminal">
```bash
>>> print(api_result)
{'date': '02-24-2022', 'milliseconds_since_epoch': 1645731229114, 'time': '07:33:49 PM'}
```
</div>

## Error handling

What happens if the Python function encounters an error while your flow is running? To see what happens whenever a flow does not complete successfully, let's intentionally run the `call_api()` flow above with a bad value for the URL:

<div class="terminal">
```bash
>>> api_result = call_api("foo")
14:34:35.687 | INFO    | prefect.engine - Created flow run 'purring-swine' for flow 'call-api'
14:34:35.687 | INFO    | Flow run 'purring-swine' - Using task runner 'ConcurrentTaskRunner'
14:34:35.710 | ERROR   | Flow run 'purring-swine' - Encountered exception during execution:
...
...
  File "/Users/terry/test/ktest/venv/lib/python3.8/site-packages/requests/models.py", line 392, in prepare_url
    raise MissingSchema(error)
requests.exceptions.MissingSchema: Invalid URL 'foo': No scheme supplied. Perhaps you meant http://foo?

```
</div>

## Run a basic flow with tasks

Let's now add some [tasks](/concepts/tasks/) to a flow so that we can orchestrate and monitor at a more granular level. 

A task is a function that represents a distinct piece of work executed within a flow. You don't have to use tasks &mdash; you can include all of the logic of your workflow within the flow itself. However, encapsulating your business logic into smaller task units gives you more granular observability, control over how specific tasks are run (potentially taking advantage of parallel execution), and the ability to reuse tasks across flows and subflows.

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
    return fact_json
```

As you can see, we still call these tasks as normal functions and can pass their return values to other tasks.  
We can then call our flow function &mdash; now called `api_flow()` &mdash; 
just as before and see the printed output. 
Prefect manages all the relevant intermediate states.

<div class="terminal">
```bash
>>> cat_fact = api_flow("https://catfact.ninja/fact")
15:10:17.955 | INFO    | prefect.engine - Created flow run 'jasper-ammonite' for flow 'api-flow'
15:10:17.955 | INFO    | Flow run 'jasper-ammonite' - Using task runner 'ConcurrentTaskRunner'
15:10:18.022 | INFO    | Flow run 'jasper-ammonite' - Created task run 'call_api-190c7484-0' for task 'call_api'
200
15:10:18.360 | INFO    | Task run 'call_api-190c7484-0' - Finished in state Completed()
15:10:18.707 | INFO    | Flow run 'jasper-ammonite' - Finished in state Completed()
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
    fact_text = parse_fact(fact_json)
    return fact_text
```

This flow should print an interesting fact about cats:

<div class="terminal">
```bash
>>> cat_fact = api_flow("https://catfact.ninja/fact")
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
    Notice in the above example that *all* of our Python logic is encapsulated within task functions. While there are many benefits to using Prefect in this way, it is not a strict requirement. Using tasks enables Prefect to automatically identify the execution graph of your workflow and provides observability of task execution in the [Prefect UI](/ui/flows-and-tasks/).

!!! warning "Tasks must be called from flows"
    All tasks must be called from within a flow. Tasks may not call other tasks directly.

## Run a flow within a flow

Not only can you call task functions within a flow, but you can also call other flow functions! Child flows are called [subflows](/concepts/flows/#subflows) and allow you to efficiently manage, track, and version common multi-task logic. See the [Subflows](/concepts/flows/#subflows) section of the Flows documentation for details.

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

The Prefect UI and Prefect Cloud provide an overview of all of your flows, flow runs, and task runs, plus a lot more. For details on using the Prefect UI, see the [Prefect UI & Prefect Cloud](/ui/overview/) documentation.

## Parameter type conversion

As with any standard Python function, you can pass parameters to your flow function, which are then used elsewhere in your flow. Prefect flows and tasks include the ability to perform type conversion for the parameters passed to your flow function. This is most easily demonstrated via a simple example:

```python
from prefect import task, flow

@task
def printer(obj):
    print(f"Received a {type(obj)} with value {obj}")

# note that we define the flow with type hints
@flow
def validation_flow(x: int, y: str):
    printer(x)
    printer(y)
```

Let's now run this flow, but provide values that don't perfectly conform to the type hints provided:

<div class="terminal">
```bash
>>> validation_flow(x="42", y=100)
Received a <class 'int'> with value 42
Received a <class 'str'> with value 100
```
</div>

You can see that Prefect coerced the provided inputs into the types specified on your flow function!  

While the above example is basic, this can be extended in powerful ways. In particular, Prefect attempts to coerce _any_ [pydantic](https://pydantic-docs.helpmanual.io/) model type hint into the correct form automatically:

```python
from prefect import flow
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@flow
def model_validator(model: Model):
    printer(model)
```

<div class="terminal">
```bash
>>> model_validator({"a": 42, "b": 0, "c": 55})
Received a <class '__main__.Model'> with value a=42 b=0.0 c='55'
```
</div>

!!! note "Parameter validation can be toggled"
    If you would like to turn this feature off for any reason, you can provide `validate_parameters=False` to your `@flow` decorator and Prefect will passively accept whatever input values you provide.

    Flow configuration is covered in more detail in the [Flow and task configuration](/tutorials/flow-task/) tutorial. For more information about pydantic type coercion, see the [pydantic documentation](https://pydantic-docs.helpmanual.io/usage/models/).

## Asynchronous functions

Even asynchronous functions work with Prefect! Here's a variation of a previous example that makes the API request as an async operation:

```python
import asyncio
import httpx
from prefect import flow, task

@task
async def call_api(url):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    return response.json()

@flow
async def async_flow(url):
    fact_json = await call_api(url)
    return fact_json
```

If we run this in the interpreter, the output looks just like previous runs.

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
result={'fact': 'Cats have about 130,000 hairs per square inch (20,155 hairs per square centimeter).', 'length': 83}
```
</div>

You can also run async tasks within non-async flows. This is a more advanced use case and will be covered in [future tutorials](/tutorials/execution/#asynchronous-execution).

!!! tip "Next steps: Flow and task configuration"
    Now that you've seen some flow and task basics, the next step is learning about [configuring your flows and tasks](/tutorials/flow-task-config/) with options such as parameters, retries, caching, and task runners.
