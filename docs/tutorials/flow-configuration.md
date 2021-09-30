# Flow and Task configuration

## Basic flow configuration

Now that we've written our first flow, let's explore various configuration options that Prefect exposes.

### Flow names

Flow names are a distinguished piece of metadata within Prefect - the name that you give to a flow becomes the unifying identifier for all future runs of that flow, regardless of version or task structure.  

### Flow descriptions

Flow descriptions allow you to provide documentation right alongside your flow object. By default, Prefect will use the flow function's docstring as a description.

### Flow versions

Flow versions allow you to associate a given run of your workflow with the version of code or configuration that was used; for example, if we were using `git` to version control our code we might use the commit hash as our version:

```python
from prefect import flow
import os

@flow(name="My Example Flow", version=os.getenv("GIT_COMMIT_SHA"))
def my_flow(...):
    ...
```

In other situations we may be doing fast iterative testing and so we might have a little more fun:

```python
@flow(name="My Example Flow", version="IGNORE ME")
def my_flow(...):
    ...
```

Ultimately, how you choose to leverage the `version` field is up to you!  By default, Prefect makes a best effort to compute a stable hash of the `.py` file in which the flow is defined so that you can detect when your code changes easily.  However, this computation is not always possible and so depending on your setup you may see that your flow has a version of `None`.


### Parameter type conversion

Many of the available configuration options for Prefect flows also allow you to configure flow execution behavior.  One such option is the ability to perform type conversion for the parameters passed to your flow function.  This is most easily demonstrated via a simple example:

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

Let's now run this flow but provide values that don't perfectly conform to the type hints provided:

<div class="termy">
```
>>> validation_flow(x="42", y=100)
Received a &#60;class 'int'&#62; with value 42
Received a &#60;class 'str'&#62; with value 100
```
</div>

You can see that Prefect coerced the provided inputs into the types specified on your flow function!  

While the above example is basic, this can be extended in incredibly powerful ways - in particular, _any_ pydantic model type hint will be automatically coerced into the correct form:

```python
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@flow
def model_validator(model: Model):
    printer(model)
```

<div class="termy">
```
>>> model_validator({"a": 42, "b": 0, "c": 55})
Received a &#60;class '__main__.Model'&#62; with value a=42 b=0.0 c='55'
```
</div>

As we will see, this pattern is particularly useful when triggering flow runs via Orion's API - all that you need is to provide a JSON document that your flow parameters can interpret and Prefect will take care of the rest.

!!! note "This behavior can be toggled"
    If you would like to turn this feature off for any reason, you can provide `validate_parameters=False` to your flow decorator and Prefect will passively accept whatever input values you provide.

    For more information, please refer to the pydantic's [official documentation](https://pydantic-docs.helpmanual.io/usage/models/).

### Flow state determination

Describe the rules of final flow state determination:
- returning task values
- returning states
- returning raw values

## Basic Task configuration

By design, tasks follow a very similar metadata model to flows: we can independently assign tasks their own name, description, and even version!  Ultimately tasks are the genesis for much of the granular control and observability that Prefect provides.

### Retries

Prefect allows for off-the-shelf configuration of task level retries.  The only two decisions we need to make are how many retries we want to attempt and what delay we need between run attempts:

```python
@task(retries=2, retry_delay_seconds=0)
def failure():
    print('running')
    raise ValueError("bad code")

@flow
def test_retries():
    return failure()
```

<div class="termy">
```
>>> test_retries()
running
running
running
```
</div>

Once we dive deeper into state transitions and orchestration policies, we will see that this task run actually went through the following state transitions: `Pending` -> `Running` -> `Awaiting Retry` -> `Retrying` some number of times.  Metadata such as this allows for a full reconstruction of what happened with your flows and tasks on each run.

### Caching

Caching refers to the ability of a task run to reflect a finished state without actually running the code that defines the task - this allows you to efficiently reuse results of tasks that may be particularly "expensive" to run with every flow run.  Moreover, Prefect makes it easy to share these states across flow and flow runs using the concept of a "cache key".  

To illustrate:
```python
def static_cache_key(context, parameters):
    # return a constant
    return "static cache key"

@task(cache_key_fn=static_cache_key)
def cached_task():
    print('running an expensive operation')
    return 42

@task
def printer(val):
    print(val)

@flow
def test_caching():
    cached_task()
    cached_task()

@flow
def another_flow():
    printer(cached_task())
```

<div class="termy">
```
>>> test_caching()
running an expensive operation
>>> another_flow()
42
```
</div>

Notice that the `cached_task` only ran one time across both flow runs!  Whenever each task run requested to enter a `Running` state, it provided its cache key computed from the `cache_key_fn`.  The Orion backend identified that there was a Completed state associated with this key and thus instructed the run to immediately enter the same state, including the same return values.  

Caching can be configured further in the following ways:

- a generic `cache_key_fn` is a function that accepts two positional arguments: 
    - the first argument corresponds to the `TaskRunContext` which is a basic object with attributes `task_run_id`, `flow_run_id`, and `task`
    - the second argument correponds to a dictionary of input values to the task; e.g., if your task is defined with signature `fn(x, y, z)` then the dictionary will have keys `"x"`, `"y"`, and `"z"` with corresponding values that can be used to compute your cache key
- by providing a `cache_expiration` represented as a `datetime.timedelta`, the cache can be configured to expire after the specified amount of time from its creation

!!! warning "The persistence of state"
    Note that up until now we have run all of our workflows interactively; this means that our metadata store is a SQLite database located at the default database location: `~/.prefect/orion.db`.  As we will see, this can be configured in various ways.  But please note that any cache keys you experiment with will be persisted in this SQLite database until you clear it manually!

!!! tip "Additional Reading"
    To learn more about the concepts presented here, check out the following resources:

    - Orchestration Policies
    - [Flows](/concepts/flows/)
    - [Tasks](/concepts/tasks/)
    - [States](/concepts/states/)
