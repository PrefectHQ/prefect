# Flow and Task configuration

## Basic flow configuration

Now that we've written our first flow, let's explore various configuration options that Prefect exposes.

### Flow names

Flow names are a distinguished piece of metadata within Prefect - the name that you give to a flow becomes the unifying identifier for all future runs of that flow, regardless of version or task structure.  

### Flow descriptions

Flow descriptions allow you to track usage documentation right alongside your flow object

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

Many of the available configuration options for Prefect flows also allow you to configure flow execution behavior.  A particularly powerful option is the ability to perform type conversion for the parameters passed to your flow function.  This is most easily demonstrated via a simple example:

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

As we will see, this pattern is particularly powerful when triggering flow runs via Orion's API - all that you need is to provide a JSON document that your flow parameters can interpret and Prefect will take care of the rest.

!!! note "This behavior can be toggled"
    If you would like to turn this feature off for any reason, you can provide `validate_parameters=False` to your flow decorator and Prefect will passively accept whatever input values you provide.

For more information, please refer to the pydantic's [official documentation](https://pydantic-docs.helpmanual.io/usage/models/).

## Basic Task configuration

By design, tasks follow a very similar metadata model to flows: we can independently assign tasks their own name, description, and even version!

But now we get to the feature set of Prefect and why you would use tasks at all - retries, caching.  

### Retries and Caching

!!! warning "The persistence of state"
    Note that up until now we have run all of our workflows interactively; this means that our metadata store that includes things like
    `Cached` states is torn down after we exit our Python session.  To persist sunch information across sessions, we need to standup a persistent database.
