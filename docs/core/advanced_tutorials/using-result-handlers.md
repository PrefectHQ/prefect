---
sidebarDepth: 0
---

# Using Result Handlers <Badge text="Deprecated in 0.11.0"/>

Let's take a look at using result handlers. As introduced in the concept documentation ["Results and Result Handlers"](../concepts/results.md), Prefect tasks associate their return value with a `Result` object attached to a task's `State`, and they can be extended with `ResultHandler`s that, when enabled, persist results to storage as a pickle into one of the supported storage backends.

Why would you use result handlers in the first place? One common situation is to allow for inspection of intermediary data when debugging flows (including -- maybe especially -- production ones). By checkpointing data during different data transformation Tasks, runtime data bugs can be tracked down by analyzing the checkpoints sequentially.

## Setting up to handle results

Checkpointing must be enabled for result handlers to be called. You must enable in two places: globally for the Prefect installation, and at the task level by providing a result handler to tasks either through its flow initialization or as a task-level override. Depending on which results handlers you configure, you may also need to ensure your authentication credentials are set up properly. For Cloud users on Prefect 0.9.1+, some of this is handled by default.

For Core-only users or Cloud users on Prefect versions <0.9.1, you must:

- Opt-in to checkpointing globally by setting the `prefect.config.flows.checkpointing` to "True"
- Specify the result handler your tasks will use for at least one level of specificity (flow-level or task-level)

For Cloud users on Prefect version 0.9.1+:

- Checkpointing will automatically be turned on; you can disable it by passing `checkpoint=False` to each task you want to turn it off for
- A result handler that matches the storage backend of your `prefect.config.flows.storage` setting will automatically be applied to all tasks, if available; notably this is not yet supported for Docker Storage
- You can override the automatic result handler at the global level, flow level, or task level

#### Setting result handler at the flow level
```bash
export PREFECT__FLOWS__CHECKPOINTING=true
```

```python{8-9}
# flow.py
from prefect.engine.result_handlers import LocalResultHandler

@task
def add(x, y=1):
    return x + y

# send the configuration to the Flow object
with Flow("my handled flow!", result_handler=LocalResultHandler()):
    first_result = add(1, y=2)
    second_result = add(x=first_result, y=100)
```

#### Setting result handler at the task level

```bash
export PREFECT__FLOWS__CHECKPOINTING=true
```

```python{4-5,13-14}
# flow.py
from prefect.engine.result_handlers import LocalResultHandler

# configure on the task decorator
@task(result_handler=LocalResultHandler())
def add(x, y=1):
    return x + y

class AddTask(Task):
        def run(self, x, y):
            return x + y

# or when instantiating a Task object
a = AddTask(result_handler=LocalResultHandler())

with Flow("my handled flow!"):
    first_result = add(1, y=2)
    second_result = add(x=first_result, y=100)
```

## Choosing your result handlers

In the above examples, we only used the `LocalResultHandler` class. This is one of several result handlers that integrate with different storage backends; the full list is in the API docs for [prefect.engine.results_handler](../../api/latest/engine/result_handlers.html) and more details on this interface is described in the concept ["Results and Result Handlers"](../concepts/results.md) documentation.

We can write our own result handlers as long as they extend the [`ResultHandler`](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/engine/result_handlers/result_handler.py) interface, or we can pick an existing implementation from Prefect Core that utilizes a storage backend we like; for example, I will use `prefect.engine.results_handler.GCSResultHandler` so that my data will be persisted in Google Cloud Storage.

## Running a flow with `GCSResultHandler`

Since the `GCSResultHandler` object must be instantiated with some initialization arguments, we utilize a flow-level override to pass in the Python object after configuring it:

```python
# flow.py
from prefect.engine.result_handlers import GCSResultHandler

gcs_handler = GCSResultHandler(bucket='prefect_results')

with Flow("my handled flow!", result_handler=gcs_handler):
    ...
```

Make sure your Prefect installation can [authenticate to Google's Cloud API](https://cloud.google.com/docs/authentication/getting-started). As long as the host of my Prefect installation can authenticate to this GCS bucket, each task's return value will be serialized into its own file in this GCS bucket.

After running my flow, I can see that my task states know the key name of their individual result storage in `Result.safe_value` when I inspect them in-memory:

```python
>>> state = flow.run()
>>> state.result[first_result]._result.safe_value
<SafeResult: '2020/2/24/21120e41-339f-4f7d-a209-82fb3b1b5507.prefect_result'>
>>> state.result[second_result]._result.safe_value
<SafeResult: '2020/2/24/133eaf17-ab77-4468-afdf-734b6540dde0.prefect_result'>
```

Using [gsutil](https://cloud.google.com/storage/docs/gsutil), I can see that those keys exist in the GCS bucket I configured my results handler to submit data to:

```bash
$ gsutil ls -r gs://prefect_results
gs://prefect_results/2020/:

gs://prefect_results/2020/2/:

gs://prefect_results/2020/2/24/:
gs://prefect_results/2020/2/24/59082506-9217-436f-9d69-9ff569b20b7a.prefect_result
gs://prefect_results/2020/2/24/a07dd6c1-837d-4925-be46-3b525be57779.prefect_result
```

If you are using Prefect Cloud, you can see that this metadata from the "safe value" is also stored and exposed in the UI:

![Task Detail with GCS Result.safe_value showing](/result-stored-in-cloud-UI-gcshandler.png)

## Running a flow with `JSONResultHandler`

A unique case is the `JSONResultHandler`, as it serializes the entire `Result` object as its `Result.safe_value`. This is only useful for small data loads and for data that Cloud users are comfortable sharing with the Cloud database. When used effectively, they can provide efficient inspection of data output in the UI. For this reason, all `Parameter` type Tasks use this as their result handler.

Let's see this with an example. The same flow that adds numbers together will instead be configured with the JSON result handler:

```python
# flow.py
from prefect.engine.result_handlers import JSONResultHandler

with Flow("my handled flow!", result_handler=JSONResultHandler()):
    ...
```

Now when I run my flow, the `Result.safe_value` contains the actual return value from my Task in it:

```python
>>> state.result[first_result]._result.value
3
>>> state.result[first_result]._result.safe_value
<SafeResult: '3'>
```

And this value `3` is also visible to Cloud users in the UI when inspecting the Task Run details:

![Task Detail with JSON Result.safe_value showing](/result-stored-in-cloud-UI-jsonhandler.png)
