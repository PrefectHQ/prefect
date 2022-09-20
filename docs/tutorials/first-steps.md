---
description: Learn the basics of creating and running Prefect flows and tasks.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - flows
    - subflows
---

# First steps

If you've never used Prefect before, let's start by exploring the core elements of Prefect workflows: flows and tasks.

If you have used Prefect 1 ("Prefect Core") and are familiar with Prefect workflows, we still recommend reading through these first steps, particularly [Run a flow within a flow](#run-a-flow-within-a-flow). Prefect 2 flows and subflows offer significant new functionality.

## Prerequisites

These tutorials assume you have [installed Prefect 2](/getting-started/installation/) in your virtual environment along with Python 3.7 or newer. 
## Flows, tasks, and subflows

Let's start with the basics, defining the central components of Prefect workflows.

A [flow](/concepts/flows/) is the basis of all Prefect workflows. A flow is a Python function decorated with a `@flow` decorator. 

A [task](/concepts/tasks/) is a Python function decorated with a `@task` decorator. Tasks represent distinct pieces of work executed within a flow. 

All Prefect workflows are defined within the context of a flow. Every Prefect workflow must contain at least one flow function that serves as the entrypoint for execution of the flow. 

Flows can include calls to tasks as well as to child flows, which we call "subflows" in this context. At a high level, this is just like writing any other Python application: you organize specific, repetitive work into tasks, and call those tasks from flows.

## Run a basic flow

The simplest way to begin with Prefect is to import `flow` and annotate your Python function using the [`@flow`][prefect.flows.flow] decorator.

Enter the following code into your code editor, Jupyter Notebook, or Python REPL. 

```python
from prefect import flow

@flow
def my_favorite_function():
    print("What is your favorite number?")
    return 42

print(my_favorite_function())
```

Running a Prefect flow manually is as easy as calling the annotated function &mdash; in this case, the `my_favorite_function()`.

Run your code in your chosen environment. Here's what the output looks like if your run the code in a Python script:

<div class="terminal">
```bash
15:27:42.543 | INFO    | prefect.engine - Created flow run 'olive-poodle' for flow 'my-favorite-function'
15:27:42.543 | INFO    | Flow run 'olive-poodle' - Using task runner 'ConcurrentTaskRunner'
What is your favorite number?
15:27:42.652 | INFO    | Flow run 'olive-poodle' - Finished in state Completed()
42
```
</div>

Notice the log messages surrounding the expected output, "What is your favorite number?". Finally, the value returned by the function is printed. 

By adding the `@flow` decorator to a function, function calls will create a _flow run_ &mdash; the Prefect Orion orchestration engine manages flow and task state, including inspecting their progress, regardless of where your flow code runs.

In this case, the state of `my_favorite_function()` is "Completed", with no further message details. This reflects the logged message we saw earlier, `Flow run 'olive-poodle' - Finished in state Completed()`. 

## Run flows with parameters

As with any Python function, you can pass arguments. The positional and keyword arguments defined on your flow function are called _parameters_. To demonstrate, run this code:

```python
import requests
from prefect import flow

@flow
def call_api(url):
    return requests.get(url).json()

api_result = call_api("http://time.jsontest.com/")
print(api_result)
```

You can pass any parameters needed by your flow function, and you can pass [parameters on the `@flow`](/api-ref/prefect/flows/#prefect.flows.flow) decorator for configuration as well. We'll cover that in a future tutorial.

For now, we run the `call_api()` flow, passing a valid URL as a parameter. In this case, we're sending a GET request to an API that should return valid JSON in the response. To output the dicionary returned by the API call, we wrap it in a `print` function.

<div class="terminal">
```bash
13:21:08.437 | INFO    | prefect.engine - Created flow run 'serious-pig' for flow 'call-api'
13:21:08.437 | INFO    | Flow run 'serious-pig' - Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...
13:21:08.559 | INFO    | Flow run 'serious-pig' - Finished in state Completed()
{'date': '07-22-2022', 'milliseconds_since_epoch': 1658510468554, 'time': '05:21:08 PM'}
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

print(api_flow("https://catfact.ninja/fact"))
```

As you can see, we still call these tasks as normal functions and can pass their return values to other tasks.  
We can then call our flow function &mdash; now called `api_flow()` &mdash; 
just as before and see the printed output. 
Prefect manages all the intermediate states.

<div class="terminal">
```bash
14:43:56.876 | INFO    | prefect.engine - Created flow run 'berserk-hornet' for flow 'api-flow'
14:43:56.876 | INFO    | Flow run 'berserk-hornet' - Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...
14:43:56.933 | INFO    | Flow run 'berserk-hornet' - Created task run 'call_api-ded10bed-0' for task 'call_api'
14:43:56.933 | INFO    | Flow run 'berserk-hornet' - Executing 'call_api-ded10bed-0' immediately...
200
14:43:57.025 | INFO    | Task run 'call_api-ded10bed-0' - Finished in state Completed()
14:43:57.035 | INFO    | Flow run 'berserk-hornet' - Finished in state Completed()
{'fact': 'Cats eat grass to aid their digestion and to help them get rid of any fur in their stomachs.', 'length': 92}
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
    fact = response["fact"]
    print(fact)
    return fact

@flow
def api_flow(url):
    fact_json = call_api(url)
    fact_text = parse_fact(fact_json)
    return fact_text

api_flow("https://catfact.ninja/fact")
```

This flow should print an interesting fact about cats:

<div class="terminal">
```bash
15:21:15.227 | INFO    | prefect.engine - Created flow run 'cute-quetzal' for flow 'api-flow'
15:21:15.227 | INFO    | Flow run 'cute-quetzal' - Starting 'ConcurrentTaskRunner'; submitted tasks will be run concurrently...
15:21:15.298 | INFO    | Flow run 'cute-quetzal' - Created task run 'call_api-ded10bed-0' for task 'call_api'
15:21:15.298 | INFO    | Flow run 'cute-quetzal' - Executing 'call_api-ded10bed-0' immediately...
200
15:21:15.391 | INFO    | Task run 'call_api-ded10bed-0' - Finished in state Completed()
15:21:15.403 | INFO    | Flow run 'cute-quetzal' - Created task run 'parse_fact-6803447a-0' for task 'parse_fact'
15:21:15.403 | INFO    | Flow run 'cute-quetzal' - Executing 'parse_fact-6803447a-0' immediately...
All cats have three sets of long hairs that are sensitive to pressure - whiskers, eyebrows,and the hairs between their paw pads.
15:21:15.429 | INFO    | Task run 'parse_fact-6803447a-0' - Finished in state Completed()
15:21:15.443 | INFO    | Flow run 'cute-quetzal' - Finished in state Completed()
```
</div>

!!! note "Combining tasks with arbitrary Python code"
    Notice in the above example that *all* of our Python logic is encapsulated within task functions. While there are many benefits to using Prefect in this way, it is not a strict requirement. Using tasks enables Prefect to automatically identify the execution graph of your workflow and provides observability of task execution in the [Prefect UI](/ui/flows-and-tasks/).

!!! warning "Tasks must be called from flows"
    All tasks must be called from within a flow. Tasks may not call other tasks directly.

## Run a flow within a flow

Not only can you call task functions within a flow, but you can also call other flow functions! Child flows are called [subflows](/concepts/flows/#composing-flows) and allow you to efficiently manage, track, and version common multi-task logic. See the [Composing flows](/concepts/flows/#composing-flows) section of the Flows documentation for details.

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

main_flow()
```

Whenever we run `main_flow` as above, a new run will be generated for `common_flow` as well.  Not only is this run tracked as a subflow run of `main_flow`, but you can also inspect it independently in the UI!

Spin up the local Prefect Orion UI using the `prefect orion start` CLI command from your terminal:

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

validation_flow(x="42", y=100)
```

Note that we are running this with flow with arguments that don't perfectly conform to the type hints provided.

For clarity in future tutorial examples, the Prefect log messages in the results will only be shown where they are relevant to the discussion.

<div class="terminal">
```bash
Received a <class 'int'> with value 42
Received a <class 'str'> with value 100
```
</div>

You can see that Prefect coerced the provided inputs into the types specified on your flow function!  

While the above example is basic, this can be extended in powerful ways. In particular, Prefect attempts to coerce _any_ [pydantic](https://pydantic-docs.helpmanual.io/) model type hint into the correct form automatically:

```python
from prefect import flow, task
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@task
def printer(obj):
    print(f"Received a {type(obj)} with value {obj}")

@flow
def model_validator(model: Model):
    printer(model)

model_validator({"a": 42, "b": 0, "c": 55})
```

<div class="terminal">
```bash
Received a <class '__main__.Model'> with value a=42 b=0.0 c='55'
```
</div>

!!! note "Parameter validation can be toggled"
    If you would like to turn this feature off for any reason, you can provide `validate_parameters=False` to your `@flow` decorator and Prefect will passively accept whatever input values you provide.

    Flow configuration is covered in more detail in the [Flow and task configuration](/tutorials/flow-task/) tutorial. For more information about pydantic type coercion, see the [pydantic documentation](https://pydantic-docs.helpmanual.io/usage/models/).


!!! tip "Next steps: Flow and task configuration"
    Now that you've seen some flow and task basics, the next step is learning about [configuring your flows and tasks](/tutorials/flow-task-config/) with options such as parameters, retries, caching, and task runners.
