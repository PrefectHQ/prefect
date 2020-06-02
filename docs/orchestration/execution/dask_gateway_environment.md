# Dask Gateway Environment

[[toc]]

## Overview

The Dask Gateway Environment executes each Flow run on a dynamically created Dask cluster. It uses
the [Dask Gateway](https://gateway.dask.org/) project to create a Dask scheduler and
workers using a central `Gatewayy` instance. This Environment aims to provide a very
easy way to achieve high scalability without bogging users down in the details of managing and
maintaining their own Dask clusters.

## Process

### Initialization

The `DaskGatewayEnvironment` requires only a `Gateway` address, and from there is
responsible for leveraging the `Gateway` to spin up and spin down independent compute clusters.

```python
from prefect import Flow, task
from prefect.environments import DaskGatewayEnvironment

environment=DaskGatewayEnvironment(
    gateway_address="https://your.gateway.domain.com",
    adaptive_min_workers=1,
)
```

The above code will create a Dask scheduler and turn on the cluster's `adaptive` mode, spinning up
a single worker. If `adaptive_min_workers` is set to `None`, then it will default to 1. Likewise,
if `adaptive_max_workers` is set to `None` then it will be set to the same value as `adaptive_min_workers`.

:::warning Scheduler/Worker Startup Latency
Scheduler/Worker pod startup time can be slow and increases as your Docker
image size increases if the image isn't already cached on that node. There can
also be additional latency on top of the image pull if a new scheduler/worker triggers
an auto-scaling event and a new node has to be spun up. This means that in reality, startup
time can range from nearly instantaneous to nearly 10 minutes in a worst-case scenario.
`DaskGatewayEnvironment` is a particularly good fit for automated
deployment of scheduled Flows in a CI/CD pipeline where the infrastructure for each Flow
should be as independent as possible, e.g. each Flow could have its own docker
image, dynamically create the Dask cluster for each Flow run, etc. However, for
development and interactive testing, creating a Dask cluster manually (with Dask Gateway or otherwise) and then using
`RemoteDaskEnvironment` or just `DaskExecutor` with your flows will result
in a much better and faster development experience.
:::

#### Requirements

The Dask Gateway environment requires a fully-functioning `Gateway` instance to already be
up-and-running within your infrastructure. It's a good idea to test your `Gateway` instance
directly and confirm that it's working properly before using the `DaskGatewayEnvironment`. See [this documentation](https://gateway.dask.org/)
for more details.

Here's an example of creating a Dask cluster using Dask Gateway directly,
running a Flow on it, and then closing the cluster to tear down all resources
that were created.

```python
from dask_gateway import Gateway

from prefect import Flow, Parameter, task
from prefect.engine.executors import DaskExecutor

gateway = Gateway(address="https://your.gateway.domain.com")
cluster = gateway.new_cluster()


@task
def times_two(x):
    return x * 2


@task
def get_sum(x_list):
    return sum(x_list)


with Flow("Dask Gateway Test") as flow:
    x = Parameter("x", default=[1, 2, 3])
    y = times_two.map(x)
    results = get_sum(y)

flow.run(executor=DaskExecutor(cluster.scheduler_address),
         parameters={"x": list(range(10))})

# Tear down the Dask cluster. If you're developing and testing your flow you would
# not do this after each Flow run, but when you're done developing and testing.
cluster.shutdown()
```

You can find the URL for the Dask dashboard of your cluster in the Flow logs:

```bash
April 26th 2020 at 12:17:41pm | prefect.GatewayEnvironment
Dask cluster created. Scheduler address: tls://172.33.18.197:8786 Dashboard: http://172.33.18.197:8787
```

#### Setup

To setup the `Gateway` instance itself, read the docs [here](https://gateway.dask.org/).
The `Gateway` instance is also required to have exposed the `c.KubeClusterConfig.image` property.
More info can be found [here](https://gateway.dask.org/cluster-options.html).

#### Execute

Create a new cluster consisting of one Dask scheduler and one or more Dask workers.
By default, `DaskGatewayEnvironment` will use the same Docker image
as your Flow for the Dask scheduler and worker. This ensures that the Dask workers have the
same dependencies (python modules, etc.) as the environment where the Flow runs. This drastically
simplifies dependency management and avoids the need for separately distributing software
to Dask workers. However, there is an `image` parameter available if you would like to specify one.

Following creation of the Dask cluster, the Flow will be run using the
[Dask Executor](/api/latest/engine/executors.html#daskexecutor) pointed
to the newly-created Dask cluster. All Task execution will take place on the
Dask workers.

## Examples

### Adaptive Number of Dask Workers

The following example will execute your Flow on a cluster that uses Dask's adaptive scaling
to dynamically select the number of workers based on load of the Flow. The cluster
will start with a single worker and dynamically scale up to five workers as needed.

:::tip Dask Adaptive Mode vs. Fixed Number of Workers
While letting Dask dynamically choose the number of workers with adaptive mode is
attractive, in the case of slow startup times for workers you may cause Dask to quickly request
the maximum number of workers. You may find that manually specifying the number of
workers with `n_workers` is more effective. You can also do your own calculation
of `n_workers` based on Flow run parameters at execution time in your own `on_execute()`
callback function. (See the last code example on this page.)
:::

```python
from prefect import Flow, task, Parameter
from prefect.environments import DaskGatewayEnvironment


environment=DaskGatewayEnvironment(
    gateway_address="https://your.gateway.domain.com",
    adaptive_min_workers=1,
    adaptive_max_workers=5,
)

@task
def times_two(x):
    return x * 2


@task
def get_sum(x_list):
    return sum(x_list)


with Flow("Dask Gateway Test", environment=environment) as flow:
    x = Parameter("x", default=[1, 2, 3])
    y = times_two.map(x)
    results = get_sum(y)
```

:::tip TLS
The `DaskGatewayEnvironment` will automatically pass the cluster security object
to the `DaskExecutor`.

### Example with Docker Storage and Simple Auth

The following example registers a multi-part flow and leverages the Docker storage
environment as well as provides proper authorization for the `DaskGatewayEnvironment`.
More info on `Gateway` auth can be found [here](https://gateway.dask.org/authentication.html).

```python
import datetime
import random
from time import sleep
from os import environ as env

from dask_gateway import Gateway
from dask_gateway.auth import BasicAuth
from prefect import task, Flow
from prefect.engine.executors import DaskExecutor
from prefect.environments.storage import Docker

from dask_gateway_environment import DaskGatewayEnvironment

# Get the Dask Gateway info
gateway_address = "https://your.gateway.domain.com/"
password = "your_password"
auth = BasicAuth()
auth.password = password


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


@task
def list_sum(arr):
    return sum(arr)


with Flow(
    name="Dask Gateway Test Flow",
    storage=Docker(
        base_image="your.base.image.io/gateway-test:1",
        registry_url="your.base.image.io",
        image_name="gateway-test-prefect",
        image_tag="1",
    ),
    environment=DaskGatewayEnvironment(
        gateway_address=gateway_address,
        auth=auth,
        adaptive_min_workers=1,
        adaptive_max_workers=5,
    ),
) as flow:
    incs = inc.map(x=range(10))
    decs = dec.map(x=range(10))
    adds = add.map(x=incs, y=decs)
    total = list_sum(adds)


flow.register(build=True)
```
