# Common Pitfalls

## Stateful tasks

### Persisting information in a Task's run method

Information that is stored in a task's `run()` method will _not_ be available to future runs.

While this might work during local testing, you should assume that each time a Prefect task runs, it does so in a completely new environment. Even if a task is run twice, it will not have access to local state that was set during a previous run.

So, you should **NOT** do this:

```python
class BadCounterTask(Task):

    def __init__(self, **kwargs):
        self.counter = 0
        super().__init__(**kwargs)

    def run(self):
        self.counter += 1 # this won't have the intended effect
        return self.counter
```

## Serialization

### Task Results and Inputs

Most of the underlying communication patterns within Prefect require that objects can be _serialized_ into some format (typically, JSON or binary). For example, when a task returns a data payload, the result will be serialized using `cloudpickle` to communicate with other `dask` workers. Thus you should try to ensure that all results and objects that you create and submit to Prefect can be serialized appropriately. Oftentimes, (de)serialization errors can be incredibly cryptic.

### Entire Flows

Moreover, when creating and submitting new flows for deployment, you should check to ensure your flow can be properly serialized and deserialized. To help you with this, Prefect has a builtin `is_serializable` utility function for giving you some confidence that your Flow can be handled:

```python
from prefect.utilities.debug import is_serializable


is_serializable(my_flow) # returns True / False
```

Note that this is _not_ a guarantee, but merely a helper to catch issues early on.

!!! tip 
    A good rule of thumb is that every object / function you rely on should either be explicitly attached to some attribute of the flow (e.g., a task) or importable via some library that is included in your `Docker` storage requirements.
:::

A more robust (albeit longer) process to check that your Flow makes it through the serialization and deployment is to build its `Docker` storage locally and check that the Flow can be deserialized within the container. For details on how to do this, see the corresponding section in the [local debugging](../advanced_tutorials/local-debugging.html#locally-check-your-flow-s-docker-storage) tutorial.
