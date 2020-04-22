# Remote Dask Environment

[[toc]]

## Overview

The Remote Dask Environment (`RemoteDaskEnvironment`) executes Flows on an existing Dask cluster. To do this, it connects to the scheduler of an existing Dask cluster and submits tasks to be run. For Prefect users who want to control the scaling characteristics of their Flows they can create a Dask cluster directly and then use this environment to execute Flows on it. See [Dask Cluster on Kubernetes](orchestration/recipes/k8s_dask.html#dask-cluster-on-kubernetes) for an example of configuring a Dask cluster.

For more information on the Remote Dask Environment visit the relevant [API documentation](/api/latest/environments/execution.html#remotedaskenvironment).

## Process

#### Initialization

The `RemoteDaskEnvironment` requires the argument `address` for the URL of a Dask scheduler. It optionally accepts a populated Dask `Security` object from `distributed.security.Security`. See [Dask TLS/SSL](https://distributed.dask.org/en/latest/tls.html) for more details. We also provide a code example of using TLS encryption with a Dask cluster below.

#### Setup

The `RemoteDaskEnvironment` has no setup step because it has no infrastructure requirements.

#### Execute

You can run your Flow on a Dask cluster simply by passing the address of the Dask scheduler in as the `address` argument to this environment.

## Examples

#### Remote Dask Environment

The follwing example shows the simplest way to run Flows on an existing Dask cluster.
```python
from prefect import task, Flow
from prefect.environments import RemoteDaskEnvironment


@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)


flow = Flow(
    "Local Executor Remote Example",
    environment=RemoteDaskEnvironment(address="tcp://127.0.0.1:8786"),  # Address of a Dask scheduler
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```

#### Remote Dask Environment with TLS encryption

```python
from distributed.security import Security

from prefect import task, Flow
from prefect.environments import RemoteDaskEnvironment
from prefect.environments.storage import Docker

@task
def get_value():
    return "Example!"


@task
def output_value(value):
    print(value)

security = Security(tls_ca_file='cluster_ca.pem',
                    tls_client_cert='cli_cert.pem',
                    tls_client_key='cli_key.pem',
                    require_encryption=True)

flow = Flow(
    "Remote Dask Environment Example",
    environment=RemoteDaskEnvironment(
        address="tls://127.0.0.1:8786",  # Address of a Dask scheduler
        security=security,
    ),
    storage=Docker(
        registry_url="gcr.io/dev/", image_name="k8s-job-flow", image_tag="0.1.0"
    ),
)

# set task dependencies using imperative API
output_value.set_upstream(get_value, flow=flow)
output_value.bind(value=get_value, flow=flow)
```
