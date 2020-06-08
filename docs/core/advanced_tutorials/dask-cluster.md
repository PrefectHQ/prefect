---
sidebarDepth: 0
---

# Deployment: Dask

> How can you run a Prefect flow in a [distributed Dask cluster](https://distributed.readthedocs.io/en/latest/)?

## The Dask Executor

Prefect exposes a suite of ["Executors"](../../api/latest/engine/executors.html) that represent the logic for how and where a task should run (e.g., should it run in a subprocess? on a different computer?). 
In our case, we want to use Prefect's `DaskExecutor` to submit task runs to a known Dask cluster. This provides a few key benefits out of the box:

- Dask manages all "intra-flow scheduling" for a single run, such as determining when upstream tasks are complete before attempting to run a downstream task. This enables users to deploy flows with many bite-sized tasks in a way that doesn't overload any central scheduler.
- Dask handles many resource decisions such as what worker to submit a job to
- Dask handles worker/scheduler communication, like serializing data between workers

## An Example Flow

If you'd like to kick the tires on Dask locally, you can [install Dask distributed](https://distributed.readthedocs.io/en/latest/install.html) and spin up a local "cluster" with two Dask workers via the following CLI commands:

```bash
> dask-scheduler
# Scheduler at: tcp://10.0.0.41:8786

# in new terminal windows
> dask-worker tcp://10.0.0.41:8786
> dask-worker tcp://10.0.0.41:8786
```

Once you have a cluster up and running, let's deploy a very basic flow that runs on this cluster. This example was repurposed from the [distributed documentation](https://distributed.readthedocs.io/en/latest/web.html#example-computation):

```python
from prefect import task, Flow
import datetime
import random
from time import sleep


@task
def inc(x):
    sleep(random.random() / 10)
    return x + 1


@task
def dec(x):
    sleep(random.random() / 10)
    return x - 1


@task
def add(x, y):
    sleep(random.random() / 10)
    return x + y


@task(name="sum")
def list_sum(arr):
    return sum(arr)


with Flow("dask-example") as flow:
    incs = inc.map(x=range(100))
    decs = dec.map(x=range(100))
    adds = add.map(x=incs, y=decs)
    total = list_sum(adds)
```

So far, all we have done is define a flow that contains all the necessary information for how to run these tasks -- none of our custom task code has been executed yet. 
To have this flow run on our Dask cluster, all we need to do is provide an appropriately configured `DaskExecutor` to the `flow.run()` method:

```python
from prefect.engine.executors import DaskExecutor

executor = DaskExecutor(address="tcp://10.0.0.41:8786")
flow.run(executor=executor)
```

If you happen to have `bokeh` installed, you can visit the [Dask Web UI](https://distributed.readthedocs.io/en/latest/web.html) and see your tasks being processed when the flow run begins!

::: tip Advanced Dask Configuration

To interface with a secure, production-hardened Dask cluster via [Dask Gateway](https://gateway.dask.org/) you may need to provide TLS details to the `DaskExecutor`. These details can be found on the [GatewayCluster object on creation](https://gateway.dask.org/usage.html#usage-create-new-cluster):

```python
from dask_gateway import Gateway
from prefect.engine.executors import DaskExecutor

# ...flow definition...

gateway = Gateway()
cluster = gateway.new_cluster()
executor = DaskExecutor(
    address=cluster.scheduler_address,
    client_kwargs={"security": cluster.security}
)
flow.run(executor=executor)
```

Alternatively, TLS details can be provided manually:

```python
from dask_gateway.client import GatewaySecurity
from prefect.engine.executors import DaskExecutor

# ...flow definition...

security = GatewaySecurity(tls_cert="path-to-cert", tls_key="path-to-key")
executor = DaskExecutor(
    address="a-scheduler-address",
    client_kwargs={"security": security}
)
flow.run(executor=executor)
```

:::

## Next Steps

Let's take this one step further: let's attach a schedule to this flow, and package it up so that we can point it to any Dask cluster we choose, without editing the code which defines the flow. To do this, we will first add a main method to our script above so that it can be executed via CLI:

```python
def main():
    from prefect.schedules import IntervalSchedule

    every_minute = IntervalSchedule(start_date=datetime.datetime.utcnow(),
                                    interval=datetime.timedelta(minutes=1))
    flow.schedule = every_minute
    flow.run() # runs this flow on its schedule


if __name__ == "__main__":
    main()
```

Notice that we didn't specify an executor in our call to `flow.run()`. This is because the default executor can be set via environment variable (for more information on how this works, see [Prefect's documentation](../concepts/configuration.html)). Supposing we save this in a file called `dask_flow.py`, we can now specify the executor and the Dask scheduler address as follows:

```bash
> export PREFECT__ENGINE__EXECUTOR__DEFAULT_CLASS="prefect.engine.executors.DaskExecutor"
> export PREFECT__ENGINE__EXECUTOR__DASK__ADDRESS="tcp://10.0.0.41:8786"

> python dask_flow.py
```

This flow will now run every minute on your local Dask cluster until you kill this process.

## Further steps

Take this example to the next level by storing your flow in a Docker container and deploying it with Dask on Kubernetes using the excellent [dask-kubernetes](http://kubernetes.dask.org/en/latest/) project!
