# First Steps

Before we stand up our own Orion webserver and database, let's explore the building blocks of a Prefect workflow via an interactive Python session.  All code below is copy / pastable into your favorite async-compatible Python REPL.

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
    for orchestration rules as well as an interface for client-side logic.


### Error handling

We can see what happens whenever our flow does not complete successfully by running the simple `send_post` flow above with a bad value for the URL:
<div class="termy">
```
>>> state = my_favorite_function()
This function doesn't do much
>>> print(state)
State(name='Completed', type=StateType.COMPLETED)
```
</div>

## Run a basic flow with tasks
