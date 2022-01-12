# First steps

If you've never used Prefect before, let's start by exploring the building blocks of a Prefect workflow flows and tasks via an interactive Python session. For these first steps, you can copy and paste the code below into your favorite async-compatible Python REPL.

If you have used Prefect Core and are familiar with Prefect workflows, we still recommend reading through these first steps, particularly [Run a flow within a flow](#run-a-flow-within-a-flow). Orion flows and subflows offer significant new functionality.

## Define a basic flow

The simplest way to begin with Prefect is to annotate your favorite Python function using the [`@flow` decorator][prefect.flows.flow]:

```python
from prefect import flow

@flow
def my_favorite_function():
    print("This function doesn't do much")
    return 42
```

Any function will work, including those that accept arguments:

```python
import requests
from prefect import flow

@flow
def send_post(url):
    return requests.post(url).json()
```

The positional and keyword arguments defined on your flow function are called _parameters_.

!!! note "Asynchronous functions"
    Even asynchronous functions work with Prefect!  We can alter the above example to be fully asynchronous using the `httpx` library:
    ```python
    import httpx
    from prefect import flow

    @flow
    async def send_post(url):
        with httpx.AsyncClient() as client:
            return await client.post(url).json()
    ```
    This is a more advanced use case and will be covered in future tutorials.

## Run a basic flow

Running a Prefect workflow manually is as easy as calling the annotated function. In this case, we're running the `my_favorite_function()` snippet shown above:

<div class="termy">
```
>>> state = my_favorite_function()
11:30:15.896 | Beginning flow run 'malachite-alligator' for flow 'my-favorite-function'...
11:30:15.896 | Starting task runner `SequentialTaskRunner`...
This function doesn't do much
11:30:15.926 | Shutting down task runner `SequentialTaskRunner`...
11:30:15.958 | Flow run 'malachite-alligator' finished in state Completed(message=None, type=COMPLETED)
```
</div>

The first thing you'll notice is the messages surrounding the expected output, "This function doesn't do much". By simply adding the `@flow` decorator to your function, the Prefect Orion orchestration engine manages task and flow state, including inspecting their progress, regardless of where your flow code runs.

For clarity in tutorial examples, we may not show these messages in results except where they are relevant to the discussion.

Next, let's print `state`, which should show us the result returned by the `my_favorite_function()` flow.

<div class="termy">
```
>>> print(state)
Completed(message=None, type=COMPLETED)
```
</div>

!!! note "Flows return states"
    You may notice that this call did not return the number 42 but rather a [Prefect `State` object][prefect.orion.schemas.states.State]. States are the basic currency of communication between Prefect clients and the Prefect API, and can be used to define the conditions for orchestration rules as well as an interface for client-side logic.  
    
    If you want to see the data returned by the flow, access it via the `.result()` method on the `State` object.

<div class="termy">
```
>>> print(state.result())
42
```
</div>

### Error handling

We can see what happens whenever our flow does not complete successfully by running the simple `send_post` flow above with a bad value for the URL:

<div class="termy">
```
>>> state = send_post("foo")
12:14:15.808 | Beginning flow run 'determined-bloodhound' for flow 'send-post'...
12:14:15.808 | Starting task runner `SequentialTaskRunner`...
12:14:15.843 | Flow run 'determined-bloodhound' encountered exception:
Traceback (most recent call last): ...
requests.exceptions.MissingSchema: Invalid URL 'foo': No schema supplied. Perhaps you meant http://foo?
12:14:15.850 | Shutting down task runner `SequentialTaskRunner`...
12:14:15.879 | Flow run 'determined-bloodhound' finished in state Failed(message='Flow run encountered an exception.', type=FAILED)
```
</div>

We see that in this situation the call still returns. The exception (truncated here for clarity as "Traceback (most recent call last): ...") is captured by Orion, which continues to shut down the task and flow runs normally. 

However, in contrast to the 'COMPLETED' state, we now encounter a 'FAILED' state signaling that something unexpected happened during execution.

<div class="termy">
```
>>> print(state)
Failed(message='Flow run encountered an exception.', type=FAILED)
```
</div>

As we will see, this behavior is consistent across flow runs _and_ task runs and allows users to respond to failure in a first-class way &mdash; whether by configuring orchestration rules in the Orion backend (retry logic) or by directly responding to failed states in client code.

## Run a basic flow with tasks

Let's now add some tasks to our flow so that we can orchestrate and monitor at a more granular level. Creating and adding tasks follows the exact same pattern as for flows, but using the [`@task` decorator][prefect.tasks.task] to annotate our favorite functions as tasks:

```python
from prefect import task, flow
import requests

@task
def extract_url_content(url, params=None):
    return requests.get(url, params=params).content

@task
def is_trending(trending_page, repo="prefect"):
    is_trending = repo.encode() in trending_page
    is_phrase = 'not ' if not is_trending else ' '
    print(f"{repo} is {is_phrase}trending.", "\n")
    return is_trending

@flow
def repo_trending_check(url="https://github.com/trending/python", 
                        window="daily"):
    content = extract_url_content(url, params={"since": window})
    return is_trending(content)
```

As you can see, we still call these tasks as normal functions and can pass their return values to other tasks.  We can then
call our flow function just as before and see the printed output. Prefect manages all the relevant intermediate state.

<div class="termy">
```
>>> state = repo_trending_check()
13:05:15.243 | Beginning flow run 'glistening-guan' for flow 'repo-trending-check'...
13:05:15.243 | Starting task runner `SequentialTaskRunner`...
13:05:15.316 | Submitting task run 'extract_url_content-a29ee45f-0' to task runner...
13:05:16.254 | Task run 'extract_url_content-a29ee45f-0' finished in state Completed(message=None, type=COMPLETED)
13:05:16.294 | Submitting task run 'is_trending-0bb0cae8-0' to task runner...
prefect is  trending.
13:05:16.363 | Task run 'is_trending-0bb0cae8-0' finished in state Completed(message=None, type=COMPLETED)
13:05:16.364 | Shutting down task runner `SequentialTaskRunner`...
13:05:16.390 | Flow run 'glistening-guan' finished in state Completed(message='All states completed.', type=COMPLETED)
```
</div>

!!! note "Combining task code with arbitrary Python code"
    Notice in the above example that *all* of our Python logic is encapsulated within task functions. While there are many benefits to using Prefect in this way, it is not a strict requirement.  Interacting with the results of your Prefect tasks requires an understanding of [Prefect futures](/api-ref/prefect/futures/), which will be covered in a [later section](/tutorials/futures-and-parallelism/).

## Run a flow within a flow

Not only can you call _task_ functions within a flow, but you can also call other flow functions! Flows that run within other flows are called **subflows** and allow you to efficiently manage, track, and version common multi-task logic.  

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

# run the flow
flow_state = main_flow()
```

Whenever we run `main_flow` as above, a new run will be generated for `common_flow` as well.  Not only is this run tracked as a subflow run of `main_flow`, but you can also inspect it independently in the UI!  

You can confirm this for yourself by spinning up the UI using the `prefect orion start` CLI command from your terminal:

<div class="termy">
```
$ prefect orion start
```
</div>

Open the URL for the Orion UI ([http://127.0.0.1:4200](http://127.0.0.1:4200) by default) in a browser. You should see all of the runs that we have run throughout this tutorial, including one for `common_flow`:

<figure markdown=1>
![](/img/tutorials/first-steps-ui.png){: max-width=600px}
</figure>

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Flows](/concepts/flows/)
    - [Tasks](/concepts/tasks/)
    - [States](/concepts/states/)
