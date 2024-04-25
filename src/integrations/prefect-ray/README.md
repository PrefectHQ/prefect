# prefect-ray

<p align="center">
    <!--- Insert a cover image here -->
    <!--- <br> -->
    <a href="https://pypi.python.org/pypi/prefect-ray/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-ray?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-ray/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-ray?color=26272B&labelColor=090422" /></a>
</p>

## Welcome!
Visit the full docs [here](https://PrefectHQ.github.io/prefect-ray) to see additional examples and the API reference.

`prefect-ray` contains Prefect integrations with the [Ray](https://www.ray.io/) execution framework, a flexible distributed computing framework for Python.

Provides a `RayTaskRunner` that enables Prefect flows to run tasks execute tasks in parallel using Ray.

## Getting Started

### Python setup

Requires an installation of Python 3.8 or newer.

We recommend using a Python virtual environment manager such as pipenv, conda, or virtualenv.

These tasks are designed to work with Prefect 2.0+. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Installation

Install `prefect-ray` with `pip`:

```bash
pip install prefect-ray
```

Users running Apple Silicon (such as M1 macs) should check out the Ray docs [here](https://docs.ray.io/en/master/ray-overview/installation.html#m1-mac-apple-silicon-support) for more details.

## Running tasks on Ray

The `RayTaskRunner` is a [Prefect task runner](https://docs.prefect.io/concepts/task-runners/) that submits tasks to [Ray](https://www.ray.io/) for parallel execution. 

By default, a temporary Ray instance is created for the duration of the flow run.

For example, this flow counts to 3 in parallel.

```python
import time

from prefect import flow, task
from prefect_ray import RayTaskRunner

@task
def shout(number):
    time.sleep(0.5)
    print(f"#{number}")

@flow(task_runner=RayTaskRunner)
def count_to(highest_number):
    for number in range(highest_number):
        shout.submit(number)

if __name__ == "__main__":
    count_to(10)

# outputs
#3
#7
#2
#6
#4
#0
#1
#5
#8
#9
```

If you already have a Ray instance running, you can provide the connection URL via an `address` argument.

To configure your flow to use the `RayTaskRunner`:

1. Make sure the `prefect-ray` collection is installed as described earlier: `pip install prefect-ray`.
2. In your flow code, import `RayTaskRunner` from `prefect_ray.task_runners`.
3. Assign it as the task runner when the flow is defined using the `task_runner=RayTaskRunner` argument.

For example, this flow uses the `RayTaskRunner` with a local, temporary Ray instance created by Prefect at flow run time.

```python
from prefect import flow
from prefect_ray.task_runners import RayTaskRunner

@flow(task_runner=RayTaskRunner())
def my_flow():
    ... 
```

This flow uses the `RayTaskRunner` configured to access an existing Ray instance at `ray://192.0.2.255:8786`.

```python
from prefect import flow
from prefect_ray.task_runners import RayTaskRunner

@flow(task_runner=RayTaskRunner(address="ray://192.0.2.255:8786"))
def my_flow():
    ... 
```

`RayTaskRunner` accepts the following optional parameters:

| Parameter | Description |
| --- | --- |
| address | Address of a currently running Ray instance, starting with the [ray://](https://docs.ray.io/en/master/cluster/ray-client.html) URI. |
| init_kwargs | Additional kwargs to use when calling `ray.init`. |

Note that Ray Client uses the [ray://](https://docs.ray.io/en/master/cluster/ray-client.html) URI to indicate the address of a Ray instance. If you don't provide the `address` of a Ray instance, Prefect creates a temporary instance automatically.

!!! warning "Ray environment limitations"
    Ray support for non-x86/64 architectures such as ARM/M1 processors with installation from `pip` alone and will be skipped during installation of Prefect. It is possible to manually install the blocking component with `conda`. See the [Ray documentation](https://docs.ray.io/en/latest/ray-overview/installation.html#m1-mac-apple-silicon-support) for instructions.

    See the [Ray installation documentation](https://docs.ray.io/en/latest/ray-overview/installation.html) for further compatibility information.

## Running tasks on a Ray remote cluster

When using the `RayTaskRunner` with a remote Ray cluster, you may run into issues that are not seen when using a local Ray instance. To resolve these issues, we recommend taking the following steps when working with a remote Ray cluster:

1. By default, Prefect will not persist any data to the filesystem of the remote ray worker. However, if you want to take advantage of Prefect's caching ability, you will need to configure a remote result storage to persist results across task runs. 

We recommend using the [Prefect UI to configure a storage block](https://docs.prefect.io/concepts/blocks/) to use for remote results storage.

Here's an example of a flow that uses caching and remote result storage:
```python
from typing import List

from prefect import flow, get_run_logger, task
from prefect.filesystems import S3
from prefect.tasks import task_input_hash
from prefect_ray.task_runners import RayTaskRunner


# The result of this task will be cached in the configured result storage
@task(cache_key_fn=task_input_hash)
def say_hello(name: str) -> None:
    logger = get_run_logger()
    # This log statement will print only on the first run. Subsequent runs will be cached.
    logger.info(f"hello {name}!")
    return name


@flow(
    task_runner=RayTaskRunner(
        address="ray://<instance_public_ip_address>:10001",
    ),
    # Using an S3 block that has already been created via the Prefect UI
    result_storage="s3/my-result-storage",
)
def greetings(names: List[str]) -> None:
    for name in names:
        say_hello.submit(name)


if __name__ == "__main__":
    greetings(["arthur", "trillian", "ford", "marvin"])
```

2. If you get an error stating that the module 'prefect' cannot be found, ensure `prefect` is installed on the remote cluster, with:
```bash
pip install prefect
```

3. If you get an error with a message similar to "File system created with scheme 's3' could not be created", ensure the required Python modules are installed on **both local and remote machines**. The required prerequisite modules can be found in the [Prefect documentation](https://docs.prefect.io/guides/deployment/storage-guide). For example, if using S3 for the remote storage:
```bash
pip install s3fs
```

4. If you are seeing timeout or other connection errors, double check the address provided to the `RayTaskRunner`. The address should look similar to: `address='ray://<head_node_ip_address>:10001'`:
```bash
RayTaskRunner(address="ray://1.23.199.255:10001")
```

## Specifying remote options

The `remote_options` context can be used to control the task’s remote options.

For example, we can set the number of CPUs and GPUs to use for the `process` task:

```python
from prefect import flow, task
from prefect_ray.task_runners import RayTaskRunner
from prefect_ray.context import remote_options

@task
def process(x):
    return x + 1


@flow(task_runner=RayTaskRunner())
def my_flow():
    # equivalent to setting @ray.remote(num_cpus=4, num_gpus=2)
    with remote_options(num_cpus=4, num_gpus=2):
        process.submit(42)
```