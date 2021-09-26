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
```
</div>

### Error handling

## Run a basic flow with tasks
