# Common Pitfalls

## Serialization

### Task Results and Inputs
Most of the underlying communication patterns within Prefect require that objects can be _serialized_ into some format (typically, JSON or binary).  For example, when a task returns a data payload, the result will be serialized using `cloudpickle` to communicate with other `dask` workers.  Thus you should try to ensure that all results and objects that you create and submit to Prefect can be serialized appropriately.  Oftentimes, (de)serialization errors can be incredibly cryptic.  

### Entire Flows
Moreover, when creating and submitting new flows for deployment, you should check to ensure your flow can be properly serialized and deserialized.  To help you with this, Prefect has a builtin `is_deployable` utility function for giving you some confidence that your Flow can be handled:
```python
from prefect.utilities.tests import is_deployable


is_deployable(my_flow) # returns True / False
```
Note that this is _not_ a guarantee, but merely a helper to catch issues early on.

::: tip
A good rule of thumb is that every object / function you rely on should either be explicitly attached to some attribute of the flow (e.g., a task) or importable via some library that is included in your `ContainerEnvironment` requirements.
:::
