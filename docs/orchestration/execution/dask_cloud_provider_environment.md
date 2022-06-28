# Dask Cloud Provider Environment

!!! warning
    Flows configured with environments are no longer supported. We recommend users transition to using [RunConfig](/orchestration/flow_config/run_configs.html) instead. See the [Flow Configuration](/orchestration/flow_config/overview.md) and [Upgrading Environments to RunConfig](/orchestration/faq/upgrade_environments.md) documentation for more information.


[[toc]]


## Overview

The Dask Cloud Provider Environment executes each Flow run on a dynamically created Dask cluster. It uses
the [Dask Cloud Provider](https://cloudprovider.dask.org/) project to create a Dask scheduler and
workers using cloud provider services, e.g. AWS Fargate. This Environment aims to provide a very
easy way to achieve high scalability without the complexity of Kubernetes.

!!! tip AWS, Azure Only
    Dask Cloud Provider currently supports AWS (using either Fargate or ECS)
    and Azure (using AzureML).
    Support for GCP is [coming soon](https://github.com/dask/dask-cloudprovider/pull/131).


!!! warning Security Considerations
    By default, Dask Cloud Provider may create a Dask cluster in some environments (e.g. Fargate)
    that is accessible via a public IP, without any authentication, and configured to NOT encrypt
    network traffic. Please be conscious of security issues if you test this environment.
    (Also see pull requests [85](https://github.com/dask/dask-cloudprovider/pull/85) and
    [91](https://github.com/dask/dask-cloudprovider/pull/91) in the Dask Cloud Provider project.)


## Process

#### Initialization

The `DaskCloudProviderEnvironment` serves largely to pass kwargs through to the specific class
from the Dask Cloud Provider project that you're using. You can find the list of
available arguments in the Dask Cloud Provider
[API documentation](https://cloudprovider.dask.org/en/latest/api.html).

```python
from dask_cloudprovider import FargateCluster

from prefect import Flow, task
from prefect.environments import DaskCloudProviderEnvironment

environment = DaskCloudProviderEnvironment(
    provider_class=FargateCluster,
    task_role_arn="arn:aws:iam::<your-aws-account-number>:role/<your-aws-iam-role-name>",
    execution_role_arn="arn:aws:iam::<your-aws-account-number>:role/ecsTaskExecutionRole",
    n_workers=1,
    scheduler_cpu=256,
    scheduler_mem=512,
    worker_cpu=512,
    worker_mem=1024
)
```

The above code will create a Dask scheduler and one Dask worker using AWS Fargate each
time that a Flow using that environment runs.


!!! warning Fargate Task Startup Latency
    AWS Fargate Task startup time can be slow and increases as your Docker
    image size increases. Total startup time for a Dask scheduler and workers can
    be several minutes. 
    
    This environment is appropriate for production
    deployments of scheduled Flows where there's little sensitivity to startup
    time. `DaskCloudProviderEnvironment` is a particularly good fit for automated
    deployment of scheduled Flows in a CI/CD pipeline where the infrastructure for each Flow
    should be as independent as possible, e.g. each Flow could have its own docker
    image, dynamically create the Dask cluster for each Flow run, etc. 
    
    However, for
    development and interactive testing, either using ECS (instead of Fargate) or
    creating a Dask cluster manually (with Dask Cloud Provider or otherwise) and then using
    `LocalEnvironment` configured with a `DaskExecutor` will result
    in a much better and faster development experience.


#### Requirements

The Dask Cloud Provider environment requires sufficient privileges with your cloud provider
in order to run Docker containers for the Dask scheduler and workers. It's a good idea to
test Dask Cloud Provider directly and confirm that it's working properly before using
`DaskCloudProviderEnvironment`. See [this documentation](https://cloudprovider.dask.org/)
for more details.

Here's an example of creating a Dask cluster using Dask Cloud Provider directly,
running a Flow on it, and then closing the cluster to tear down all cloud resoures
that were created.

```python
from dask_cloudprovider import FargateCluster

from prefect import Flow, Parameter, task
from prefect.executors import DaskExecutor

cluster = FargateCluster(
    image="prefecthq/prefect:latest",
    task_role_arn="arn:aws:iam::<your-aws-account-number>:role/<your-aws-iam-role-name>",
    execution_role_arn="arn:aws:iam::<your-aws-account-number>:role/ecsTaskExecutionRole",
    n_workers=1,
    scheduler_cpu=256,
    scheduler_mem=512,
    worker_cpu=256,
    worker_mem=512,
    scheduler_timeout="15 minutes",
)
# Be aware of scheduler_timeout. In this case, if no Dask client (e.g. Prefect
# Dask Executor) has connected to the Dask scheduler in 15 minutes, the Dask
# cluster will terminate. For development, you may want to increase this timeout.


@task
def times_two(x):
    return x * 2


@task
def get_sum(x_list):
    return sum(x_list)


with Flow("Dask Cloud Provider Test") as flow:
    x = Parameter("x", default=[1, 2, 3])
    y = times_two.map(x)
    results = get_sum(y)

# cluser.scheduler.address is the private ip 
# use cluster.scheduler_address if connecting on the public ip
flow.run(executor=DaskExecutor(cluster.scheduler.address),
         parameters={"x": list(range(10))})

# Tear down the Dask cluster. If you're developing and testing your flow you would
# not do this after each Flow run, but when you're done developing and testing.
cluster.close()
```

One of the coolest and most useful features of Dask is the visual dashboard that
updates in real time as a cluster executes a Flow. Here's a view of the Dask dashboard
while the above Flow processed a list of 100 items with 4 Dask workers:

![](/orchestration/dask/dask-cloud-provider-dashboard.png)

You can find the URL for the Dask dashboard of your cluster in the Flow logs:

```
April 26th 2020 at 12:17:41pm | prefect.DaskCloudProviderEnvironment
Dask cluster created. Scheduler address: tls://172.33.18.197:8786 Dashboard: http://172.33.18.197:8787
```

#### Setup

The Dask Cloud Provider environment has no setup step because it has no infrastructure requirements.

#### Execute

Create a new cluster consisting of one Dask scheduler and one or more Dask workers on your
cloud provider. By default, `DaskCloudProviderEnvironment` will use the same Docker image
as your Flow for the Dask scheduler and worker. This ensures that the Dask workers have the
same dependencies (python modules, etc.) as the environment where the Flow runs. This drastically
simplifies dependency management and avoids the need for separately distributing softare
to Dask workers.

Following creation of the Dask cluster, the Flow will be run using the
[Dask Executor](/api/latest/executors.html#daskexecutor) pointed
to the newly-created Dask cluster. All Task execution will take place on the
Dask workers.

## Examples

#### Adaptive Number of Dask Workers

The following example will execute your Flow on a cluster that uses Dask's adaptive scaling
to dynamically select the number of workers based on load of the Flow. The cluster
will start with a single worker and dynamically scale up to five workers as needed.

!!! tip Dask Adaptive Mode vs. Fixed Number of Workers
    While letting Dask dynamically choose the number of workers with adaptive mode is
    attractive, the slow startup time of Fargate workers may cause Dask to quickly request
    the maximum number of workers. You may find that manually specifying the number of
    workers with `n_workers` is more effective. You can also do your own calculation
    of `n_workers` based on Flow run parameters at execution time in your own `on_execute()`
    callback function. (See the last code example on this page.)


```python
from dask_cloudprovider import FargateCluster

from prefect import Flow, task, Parameter
from prefect.environments import DaskCloudProviderEnvironment

environment = DaskCloudProviderEnvironment(
    provider_class=FargateCluster,
    cluster_arn="arn:aws:ecs:us-west-2:<your-aws-account-number>:cluster/<your-ecs-cluster-name>",
    task_role_arn="arn:aws:iam::<your-aws-account-number>:role/<your-aws-iam-role-name>",
    execution_role_arn="arn:aws:iam::<your-aws-account-number>:role/ecsTaskExecutionRole",
    adaptive_min_workers=1,
    adaptive_max_workers=5,
    scheduler_cpu=256,
    scheduler_mem=512,
    worker_cpu=512,
    worker_mem=1024
)


@task
def times_two(x):
    return x * 2


@task
def get_sum(x_list):
    return sum(x_list)


with Flow("Dask Cloud Provider Test", environment=environment) as flow:
    x = Parameter("x", default=[1, 2, 3])
    y = times_two.map(x)
    results = get_sum(y)
```

#### Advanced Example: Dynamic Worker Sizing from Parameters & TLS Encryption

In this example we enable TLS encryption with Dask and dynamically calculate the number of Dask
workers based on the parameters to a Flow run just prior to execution.

- The `on_execute` callback function examines parameters for that Flow run and modifies the kwargs
that will get passed to the constructor of the provider class from Dask Cloud Provider.

- TLS ecryption requires that the cert, key, and CA files are available in the Flow's Docker image

- The `scheduler_extra_args` and `worker_extra_args` kwargs are not yet available in Dask Cloud Provider,
but there is an [open pull request](https://github.com/dask/dask-cloudprovider/pull/91) to include them.

```python
import math

from typing import Any, List, Dict

from distributed.security import Security
from dask_cloudprovider import FargateCluster

import prefect
from prefect import Flow, Parameter, task
from prefect.environments import DaskCloudProviderEnvironment


security = Security(
    tls_client_cert="/opt/tls/your-cert-file.pem",
    tls_client_key="/opt/tls/your-key-file.key",
    tls_ca_file="/opt/tls/your-ca-file.pem",
    require_encryption=True,
)


def on_execute(parameters: Dict[str, Any], provider_kwargs: Dict[str, Any]) -> None:
    length_of_x = len(parameters.get("x"))
    natural_log_of_length = int(math.log(length_of_x))
    n_workers = min(1, max(10, natural_log_of_length))  # At least 1 worker & no more than 10
    provider_kwargs["n_workers"] = n_workers


environment = DaskCloudProviderEnvironment(
    provider_class=FargateCluster,
    cluster_arn="arn:aws:ecs:us-west-2:<your-aws-account-number>:cluster/<your-ecs-cluster-name>",
    task_role_arn="arn:aws:iam::<your-aws-account-number>:role/<your-aws-iam-role-name>",
    execution_role_arn="arn:aws:iam::<your-aws-account-number>:role/ecsTaskExecutionRole",
    n_workers=1,
    scheduler_cpu=256,
    scheduler_mem=512,
    worker_cpu=512,
    worker_mem=1024,
    on_execute=on_execute,
    security=security,
    scheduler_extra_args=[
        "--tls-cert",
        "/opt/tls/your-cert-file.pem",
        "--tls-key",
        "/opt/tls/your-key-file.key",
        "--tls-ca-file",
        "/opt/tls/your-ca-file.pem",
    ],
    worker_extra_args=[
        "--tls-cert",
        "/opt/tls/your-cert-file.pem",
        "--tls-key",
        "/opt/tls/your-key-file.key",
        "--tls-ca-file",
        "/opt/tls/your-ca-file.pem",
    ]
)


@task
def times_two(x):
    return x * 2


@task
def get_sum(x_list):
    return sum(x_list)


with Flow("DaskCloudProviderEnvironment Test", environment=environment) as flow:
    x = Parameter("x", default=list(range(10)))
    y = times_two.map(x)
    results = get_sum(y)

```
