---
sidebarDepth: 0
---

# Using Result Handlers

Let's take a look at using result handlers. As introduced in the concept documentation ["Results and Result Handlers"](../concepts/results.md), Prefect Tasks associate their return value with a `Result` object attached to a Task's `State`, and they can be extended with `ResultHandler`s that, when enabled, persist results to storage as a pickle into one of the supported storage backends.

Why would you use result handlers in the first place? One common situation is to allow for inspection of intermediary data when debugging flows (including -- maybe especially -- production ones). By checkpointing data during different data transformation Tasks, runtime data bugs can be tracked down by analyzing the checkpoints sequentially.

## Setting up to handle results

The first step to getting the most out of Result Handlers is to enable results storage. You must enable in two places: globally for the Prefect installation, and at the task level by providing a result handler to tasks either through its flow initialization or as a task-level override. Depending on your storage backend, you may also need to ensure your authentication credentials are set up properly. For Cloud customers, some of this is handled by default.

For Core-only users or Cloud customers on Prefect versions <0.9.1, you must
- opt-in to checkpointing globally by setting the `prefect.config.flows.checkpointing` to "True".
- specify the result handler your tasks will use for at least one level of specificity (flow-level or task-level)

For Cloud customers on Prefect version 0.9.1+,
- checkpointing will automatically be turned on; you can disable it by setting `prefect.config.flows.checkpointing` to "False"
 - a result handler that matches the storage backend of your `prefect.config.flows.storage` setting will automatically be applied to all tasks , if available; notably this is not yet supported for Docker Storage
 - you can override the automatic results handler at the global level, flow level, or task level

#### Setting result handler at the Flow level
```bash
export PREFECT__FLOWS__CHECKPOINTING=true
```
 ```python
# flow.py

@task
def add(x, y=1):
    return x + y

# send the configuration to the Flow object
with Flow("my handled flow!", result_handler=LocalStorageHandler()):
    first_result = add(1, y=2)
    second_result = add(x=first_result, y=100)
```

#### Setting result handler at the task level
```bash
export PREFECT__FLOWS__CHECKPOINTING=true
```
 ```python
# flow.py

# configure on the task decorator
@task(result_handler=LocalStorageHandler())
def add(x, y=1):
    return x + y

with Flow("my handled flow!"):
    first_result = add(1, y=2)
    # or send as a keyword argument at task initialization
    second_result = add(x=first_result, y=100, result_handler=LocalStorageHandler())
```

## Choosing your result handlers

In the above examples, we only used the `LocalStorageHandler` class. This is one of several result handlers that integrate with different storage backends; the full list is in the API docs for [prefect.engine.results_handler](../../api/latest/engine/result_handlers.html) and more details on this interface is described in the concept ["Results and Result Handlers"](../concepts/results.md) documentation.
 
We can write our own result handlers as long as they extend the `ResultHandler` interface, or we can pick an existing implementation from Prefect Core that utilizes a storage backend we like; for example, I will use `prefect.engine.results_handler.GCSResultHandler` so that my data will be persisted in Google Cloud Storage.

## Running a flow with `GCSResultHandler`

Since the `GCSResultHandler` object must be instantiated with some initialization arguments, we utilize a flow-level override to pass in the Python object after configuring it:

 ```python
# flow.py
from prefect.engine.result_handlers import GCSResultHandler

gcs_handler = GCSResultHandler(bucket='prefect_results')

with Flow("my handled flow!", result_handler=gcs_handler):
    ...
```

Make sure your Prefect installation can authenticate to Google's Cloud API; [their documentation is here](https://cloud.google.com/docs/authentication/getting-started). As long as the host of my Prefect installation can authenticate to this GCS bucket, each task's return value will be serialized into its own file in this GCS bucket.

After running my flow, I can see that my task states know the key name of their individual result storage in `Result.safe_value` when I inspect them in-memory:

```python
>>> state = flow.run()
>>> state.result[first_result]._result.safe_value
<SafeResult: '2020/2/24/21120e41-339f-4f7d-a209-82fb3b1b5507.prefect_result'>
>>> state.result[second_result]._result.safe_value
<SafeResult: '2020/2/24/133eaf17-ab77-4468-afdf-734b6540dde0.prefect_result'>
```

And I can see that those keys exist in the GCS bucket I configured my results handler to submit data to:

```bash
$ gsutil ls -r gs://prefect_results
gs://prefect_results/2020/:

gs://prefect_results/2020/2/:

gs://prefect_results/2020/2/24/:
gs://prefect_results/2020/2/24/59082506-9217-436f-9d69-9ff569b20b7a.prefect_result
gs://prefect_results/2020/2/24/a07dd6c1-837d-4925-be46-3b525be57779.prefect_result
```

If you are also a Cloud customer, you can see that this metadata from the "safe value" is also stored by the scheduler and exposed in the UI:

![Task Detail with Result.safe_value showing](/result-stored-in-cloud-UI.png)