# Frequently Asked Questions

The questions listed here are specific to using Prefect to orchestrate flows. The [FAQ in the Core section](/core/faq.html) is for people looking to learn more about Prefect in general.

[[toc]]

### How do I set a task to be an upstream task?

When there is no data dependency between tasks, upstream tasks can be set in two ways. They are equivalent, so choose what works best for your coding style.

Method 1 (`upstream_tasks` argument):
```python
with Flow("example") as flow:
    a = first_task()
    b = second_task()
    c = third_task(c_inputs, upstream_tasks=[a,b])
```

Method 2 (`set_upstream` method):
```python
with Flow("example") as flow:
    a = first_task()
    b = second_task()
    c = third_task()
    b.set_upstream(a)
    c.set_upstream(b)
```

### Why do I get a `ModuleNotFoundError` with my home directory path?

When a flow is registered, Prefect stores the location of it in [Storage](/orchestration/flow_config/storage.html) (`GitHub`, `S3`, `Docker`, etc.). During a flow run execution, Prefect pulls the flow from the storage location and runs it. If users don’t specify any storage, it defaults to a `Local` storage, which is a serialized version of the flow stored in the `~/.prefect/flows` folder. At runtime, the flow is retrieved from this file.

The error you see usually happens when you use the default `Local` storage during the registration, and then you run the flow on a different machine (or a container) that doesn’t have the flow file.

If you are running a flow on a different machine than the one from which you registered it, you need to use a remote storage class such as one of the Git storage classes (for example, `GitHub`) or a cloud storage bucket (such as `S3`) so that the flow can be pulled from that location.

### Why is my Flow stuck in a Scheduled state?

When flows are stuck in a Scheduled state, it’s usually due to a label mismatch between the flow and agent. [Labels](/orchestration/agents/overview.html#labels) are the mechanism that dictates which flows an agent can pick up. If there is no agent that can pick up a flow, the flow remains stuck in a Scheduled state.

Tips for debugging:

- Check that the flow labels are a subset of the agent labels.
- Check that there is a healthy agent that can pick up the flow.
- Make sure that the RunConfig takes in a `List[str]` as opposed to just a string. Setting `labels="prod"` will be treated as four labels `(["p", "r", "o", "d"])` because strings are iterable in Python.
- Flows with no labels are picked up by agents with no labels only.
- There is a [default label on the LocalAgent that contains the hostname](/orchestration/agents/local.html#labels).
- There is a [default label on the default Local Storage](/orchestration/flow_config/storage.html#local).
- Check if there is a Flow Concurrency Limit preventing the flow from being picked up.

There is an edge case where the scheduler gets overwhelmed if there are more than 750 late runs in a tenant. In this case, the late runs need to be cleared for more work to be executed.

### How do I add things to the Prefect context so I can reuse them in other tasks?

The Prefect context is not meant to be mutable so adding an item to it inside a task will not take effect in downstream tasks. Often, a much better approach is to use a Parameter to contain a value that will be used or manipulated by tasks.

### Why do I get `TypeError: cannot pickle ______ object`?

There are two scenarios where this error happens. The first is when using a `DaskExecutor` and using a task input or output that is not serializable by cloudpickle. Dask uses cloudpickle as the mechanism to send data from the client to the workers. This specific error is often raised with mapped tasks that use client type objects, such as connections to databases, as inputs. These connections need to be instantiated (and closed) inside tasks instead to work around this. 

The second way this can happen is through [Prefect results](/core/concepts/results.html#results). By default, task outputs are saved as `LocalResults`, and the default serializer is the `PickleSerializer`, which uses cloudpickle. If you have a task that returns a client or connection, you can avoid this serialization by turning off checkpointing for that task which `@task(checkpoint=False)`.

### Why are the Dask logs not being shown in the Prefect UI?

Independent of Prefect, using Dask on a cluster [does not capture worker logs](https://github.com/dask/distributed/issues/2033) and send them back to the scheduler. The `LocalDaskExecutor` will show the logs in the Prefect UI because the `LocalDaskExecutor` just uses `dask` while the `DaskExecutor` uses `distributed`. 

On the Prefect side, the native Python logger gets serialized and then sent to workers. When it gets deserialized, it loses the configuration attached, so the logs are not directed to Prefect Cloud.

There are several ways you could approach this. 

1. You could set up some log aggregation service to send Dask worker logs for debugging.
2. You can view the worker logs directly.

### Is there an equivalent to Airflow sensors in Prefect? How do I trigger event-driven workflows?

Overall, there are a couple of ways how you could tackle it:

- Event based: once the event that you are looking for occurs, then trigger a specific flow to run. If you are on AWS, this event could trigger a Lambda function that triggers a flow run. The event could be a new file arrived in S3 or a new row streamed to DynamoDB, Kinesis, or AWS Aurora.
- API-based: since starting a FlowRun is just an API call, you can do that from any flow or even a task, and there is a lot that you could do with this approach. For example, if one table was updated in a task, a subsequent task could trigger another flow or make an API call to take action.
3. State based: this would work in a similar way to Airflow sensors - you raise a RETRY signal if the condition you poll for is not met.

```python
import pendulum
from prefect.engine.signals import RETRY

@task
def my_sensor(**kwargs):
    # check some state of the world
    if condition_not_met:
        raise RETRY("Condition not met, retrying in 5 seconds.", start_time=pendulum.now().add(seconds=5))
```

This can also be done with a `while` loop inside a task.

```python
@task
def my_sensor(**kwargs):
    # check some state of the world
    condition_not_met = True
    while condition_not_met:
        condition_not_met = check_condition()
    return
```

### How do I set a dynamic default value for a Parameter like a callable?

If you do something like:

```python
from datetime import date

with Flow("example") as flow:
	start_date = Parameter("start_date", default=(date.today().strftime("%Y-%m-%d"))
	do_something(start_date)
```

The default Parameter value is evaluated during registration time, so the `start_date` in the example above will be fixed to the registration date. In order to add dynamicism, using a task is needed to defer the execution of `date.today()` to runtime. For example:

```python
from datetime import date

@task
def get_date(day):
    if day == None:
        return date.today().strftime("%Y-%m-%d")
    else:
        return day

with Flow("example") as flow:
	start_date = Parameter("start_date", default=None)
    new_date = get_date(start_date)
	do_something(new_date)
```

### How can I set a custom flow run name?

The flow run name cannot be set in advance, but it can be changed using the [RenameFlowRun](api/latest/tasks/prefect.html#renameflowrun) task after the flow run has been created. You can use this task inside the flow block, or through a flow-level state handler. When calling the task from a state handler, make sure to call the task’s  `.run()` method.

Here is a flow-level state handler example:

```python
from prefect import Flow, task
from prefect.tasks.prefect import RenameFlowRun

def rename_handler(obj, new_state, old_state):
    if new_state.is_running():
        RenameFlowRun().run(flow_run_name="new_name")
    return

@task
def first_task():
    return 1

with Flow("test-flow", state_handlers=[rename_handler]) as flow:
    first_task()
```

### How do I add things to the prefect context so I can reuse them in other tasks?

The Prefect context is not meant to be mutable so adding an item to it inside a task will not take effect in downstream tasks. Often, a much better approach is to use a Parameter to contain a value that will be used or manipulated by tasks.

### How do I pull Cloud secrets instead of using local secrets?

Flow runs triggered by an agent will pull Cloud secrets by default. If you want to pull Cloud secrets during testing with `flow.run()`, you can export the environment variable:

```bash
export PREFECT__CLOUD__USE_LOCAL_SECRETS=false
```
or you can use the `config.toml` setting
```
[cloud]
use_local_secrets = false
```

### Can I run a Docker agent in a container?

In general, the Docker agent is supposed to run in a local process (rather than in a docker container), and this local process is a layer between Prefect backend and a Docker Daemon.

This agent polls the API for new flow runs, and if there are new scheduled runs, it then creates new flow runs and deploys those as Docker containers on the same machine as the agent.

When the Docker agent is running within a container itself (rather than a local process), your flow runs end up deployed as containers, but not as individual containers, but rather within the agent container. You effectively have a single agent container spinning up new containers within itself (docker in docker), which may have many unintended consequences such as issues with scale and resource utilization.

If you want more environment isolation for this agent process, you can run it within a virtual environment.

And if you have a strict requirement that every process must run in a container, consider using the [KubernetesAgent](/orchestration/agents/kubernetes.html#requirements) instead.

### How can I change the number of DaskExecutor workers based on a Parameter value?

You can pass a callable to the DaskExecutor that sizes the DaskExecutor dynamically at runtime.

```python
from prefect import Flow
from prefect.executors import DaskExecutor

def dynamic_executor():
    from distributed import LocalCluster
    # could be instead some other class e.g. from dask_cloudprovider.aws import FargateCluster
    return LocalCluster(n_workers=prefect.context.parameters["n_workers"])

with Flow("example", executor=DaskExecutor(cluster_class=dynamic_executor)) as flow:
    flow.add_task(Parameter("n_workers", default=5))
```

### How can I force a task to Fail based on a given condition?

If the task itself throws an error, the task will also fail as a result. If there is some other condition that you want to trigger a Failed state, the most direct way is by simply raising a FAIL signal:

```python
from prefect import task
from prefect.engine.signals import FAIL

@task
def my_task(condition: bool=True):
  if condition:
	  raise FAIL('this task failed')
	else:
		return "all is good"
```

### I can't connect to the Prefect Server API from other machines. What am I missing?

First, make sure that port 4200 is opened for outside connections to access. Also check that the API is working on the Server deployment by going to the Interactive API and testing that the API is healthy. The `hello` endpoint can be used as follows:

```graphql
query {
  hello
}
```

If it is working, you might need to start the Server with the expose flag as follows: `prefect server start --expose`. This will allow outside connections. You can find more information in this [Github issue](https://github.com/PrefectHQ/prefect/issues/4963).

### Why does Prefect mark flow runs with `No heartbeat detected from the remote task; marking the run as failed`?

Prefect flows have heartbeats that signal to Prefect Cloud that your flow is alive. If Prefect didn’t have heartbeats, flows that lose communication and die would be shown permanently with a Running state in the UI. Most of the time, we have seen “no heartbeat detected” to be a sign of memory issues. In version 0.15.4 and above, additional logging has been added that propagates the real error in the event this error happens. 

You can [configure heartbeats to use threads instead of processes.](/orchestration/concepts/services.html#heartbeat-configuration) This has proven to be more stable for many users. In the event that the flow continues to fail after switching to using threads, some users have had success in making the failing task a subflow, and then turning off heartbeats for the subflow.

### How do I attach other loggers to the Prefect logger?

The logging docs show how [here](/core/concepts/logging.html#extra-loggers).