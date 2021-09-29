# First Steps

Before we stand up our own Orion webserver, database, and UI let's explore the building blocks of a Prefect workflow via an interactive Python session.  All code below is copy / pastable into your favorite async-compatible Python REPL.

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

@flow
def send_post(url):
    return requests.post(url).json()
```

The arguments and keyword arguments defined on your flow function are called _parameters_.

!!! note "Asynchronous functions"
    Even asynchronous functions work with Prefect!  We can alter the above example to be fully asynchronous using the `httpx` library:
    ```python
    import httpx

    @flow
    async def send_post(url):
        with httpx.AsyncClient() as client:
            return await client.post(url).json()
    ```
    This is a more advanced use case and will be covered in future tutorials.

## Run a basic flow

Running a Prefect workflow manually is as easy as calling the annotated function:

<div class="termy">
```
>>> state = my_favorite_function()
This function doesn't do much
>>> print(state)
State(name='Completed', type=StateType.COMPLETED)
```
</div>

!!! note "Flows return states"
    You may notice that this call did not return the number 42 but rather a [Prefect State object][prefect.orion.schemas.states.State].
    States are the basic currency of communication between Prefect Clients and the Prefect API, and can be used to define the conditions 
    for orchestration rules as well as an interface for client-side logic.  Data can be accessed via the `.result` attribute on the `State` object.


### Error handling

We can see what happens whenever our flow does not complete successfully by running the simple `send_post` flow above with a bad value for the URL:
<div class="termy">
```
>>> state = send_post("foo")
>>> print(state)
State(name='Failed', type=StateType.FAILED, message='Flow run encountered an exception.')
```
</div>

We see that in this situation the call still returns without raising an exception; however, in contrast to the 'Completed' state, we now encounter a 'Failed' state signaling that something unexpected happened during execution.

As we will see, this behavior is consistent across flow runs _and_ task runs and allows users to respond to failure in a first-class way; whether by configuring orchestration rules in the Orion backend (e.g., retry logic) or by directly responding to failed states in client code.

## Run a basic flow with tasks

Let's now add some tasks to our flow so that we can orchestrate and monitor at a more granular level.  Creating and adding tasks follows the exact same pattern as for flows - using the [`@task` decorator][prefect.tasks.task] we annotate our favorite functions:

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
    print(f"{repo} is {is_phrase}trending.")
    return is_trending


@flow
def repo_trending_check(url="https://github.com/trending/python", 
                        window="daily"):
    content = extract_url_content(url, params={"since": window})
    return is_trending(content)
```

As you can see, we still call these tasks as normal functions and can pass their return values to other tasks.  We can then
call our flow function just as before and see the printed output - Prefect will manage all the relevant intermediate state.

!!! note "Combining task code with arbitrary Python code"
    Notice in the above example that *all* of our Python logic is encapsulated within task functions. While there are many benefits to using Prefect in this way, it is not a strict requirement.  Interacting with the results of your Prefect tasks requires an understanding of [Prefect futures](/api-ref/prefect/futures/) which will be covered in a [later section](/tutorials/futures-and-parallelism/).

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - [Flows](/concepts/flows/)
    - [Tasks](/concepts/tasks/)
    - [States](/concepts/states/)
