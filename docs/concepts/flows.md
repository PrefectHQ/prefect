# Flows

Flows are the most basic Prefect object. They are containers for workflow logic and allow users to interact with and reason about the state of their workflows. They are the only abstraction that can be interacted with, displayed, and run without needing to reference any other aspect of the Prefect engine.

For must use cases, we recommend using the `@flow` decorator to designate a flow:

```python hl_lines="3"
from prefect import flow

@flow
def my_flow():
    return
```

Flows are uniquely identified by name. You can provide a `name` parameter value for the flow, but if not provided, the function name is used. 

```python hl_lines="1"
@flow(name="My Flow")
def my_flow():
    return
```

## Parameters

Flows can be called with both positional and keyword arguments. These arguments are resolved at runtime into a dictionary of **parameters** mapping name to value and stored in Orion. When creating flow runs from the Orion API, parameter names must be specified when overriding defaults &mdash; they cannot be positional.

You saw an example of the `name` parameter earlier: `@flow(name="My Flow")`.

For details about supported flow parameters, see the [prefect.flows](/api-ref/prefect/flows/#prefect.flows.flow) API documentation.

Type hints provide an easy way to enforce typing on your flow parameters via [pydantic](https://pydantic-docs.helpmanual.io/).  This means _any_ pydantic model used as a type hint within a flow will be coerced automatically into the relevant object type:

```python
from pydantic import BaseModel

class Model(BaseModel):
    a: int
    b: float
    c: str

@flow
def model_validator(model: Model):
    print(model)
```

!!! note "Type hints unify API types with Python"
    Note that parameter values can be provided to a flow via API using the concept of a [deployment](/concepts/deployments/).  In general, the API only knows how to parse JSON-compatible entities, but type hints on your flow functions provide you a way of automatically coercing JSON provided values to their appropriate Python representation.  
    
    For example, to automatically convert something to a datetime:

    ```python
    from prefect import flow
    from datetime import datetime

    @flow
    def what_day_is_it(date: datetime = None):
        if date is None:
            date = datetime.utcnow()
        print(f"It was {date.strftime('%A')} on {date.isoformat()}")

    what_day_is_it("2021-01-01T02:00:19.180906")
    # It was Friday on 2021-01-01T02:00:19.180906
    ```

## Final state determination

The final state of the flow is determined by its return value.  The following rules apply:

- If an exception is raised directly in the flow function, the flow run is marked as failed.
- If the flow does not return a value (or returns `None`), its state is determined by the states of all of the tasks and subflows within it. In particular, if _any_ task run or subflow run failed, then the final flow run state is marked as failed.
- If a flow returns one or more task run futures, these runs are used as the _reference tasks_ for determining the final state of the run. If _any_ returned task runs fail, the flow run is marked as failed.
- If a flow returns a manually created state, it is used as the state of the final flow run. This allows for manual determination of final state.
- If the flow run returns _any other object_, then it is marked a successfully completed.

The following examples illustrate each of these cases:

=== "Raise an exception"

    If an exception is raised within the flow function, the flow is immediately marked as failed.

    ```python hl_lines="5"
    from prefect import flow

    @flow
    def always_fail_flow():
        raise ValueError("This flow immediately fails")
    ```

=== "Return None"

    A flow with no return statement is determined by the state of all of its task runs.

    ```python
    from prefect import flow, task

    @task
    def always_fails_task():
        raise ValueError("I am bad task")

    @task
    def always_succeeds_task():
        return "foo"

    @flow
    def always_fails_flow():
        always_fails_task()
        always_succeeds_task()
    ```

=== "Return a future"

    If a flow returns one or more futures, the final state is determined based on the underlying states.

    ```python hl_lines="15"
    from prefect import task, flow

    @task
    def always_fails_task():
        raise ValueError("I am bad task")

    @task
    def always_succeeds_task():
        return "foo"

    @flow
    def always_succeeds_flow():
        x = always_fails_task()
        y = always_succeeds_task()
        return y
    ```

=== "Return a state"

    If a flow returns one or more states, the final state is determined based on the return value.

    ```python hl_lines="16-19"
    from prefect import task, flow
    from prefect.orion.schemas.states import Completed, Failed

    @task
    def always_fails_task():
        raise ValueError("I am bad task")

    @task
    def always_succeeds_task():
        return "foo"

    @flow
    def always_succeeds_flow():
        x = always_fails_task()
        y = always_succeeds_task()
        if y.result() == "foo"
            return Completed(message="I am happy with this result")
        else:
            return Failed(message="How did this happen!?")
    ```

=== "Return an object"

    If a flow returns any other Python object, the final state is always `Completed`.

    ```python hl_lines="10"
    from prefect import task, flow

    @task
    def always_fails_task():
        raise ValueError("I am bad task")

    @flow
    def always_succeeds_flow():
        always_fails_task()
        return "foo"
    ```

## Subflows

A _subflow_ run is created when a flow function is called inside the execution of another flow. The primary flow is the "parent" flow. The flow created within the parent is the "child" flow or "subflow."

Subflow runs behave like normal flow runs. There is a full representation of the flow run in the backend as if it had been called separately. Tasks within the subflow are submitted to the subflow's executor. 

Unlike tasks, subflows will block until completion with all executors. However, asynchronous subflows can be run in parallel by using [AnyIO task groups](https://anyio.readthedocs.io/en/stable/tasks.html) or [asyncio.gather](https://docs.python.org/3/library/asyncio-task.html#id6).

Subflows differ from normal flows in that they will resolve any passed task futures into data. This allows data to be passed from the parent flow to the child easily.

The relationship between a child and parent flow is tracked by creating a special task run in the the parent flow. This task run will mirror the state of the child flow run.

A task that represents a subflow will be annotated as such in its `state_details` via the presence of a `child_flow_run_id` field.  A subflow can be identified via the presence of a `parent_task_run_id` on `state_details`.
