# prefect-kubernetes

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-kubernetes/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-kubernetes?color=26272B&labelColor=090422"></a>
    <a href="https://pypistats.org/packages/prefect-kubernetes/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-kubernetes?color=26272B&labelColor=090422" /></a>
</p>


## Welcome!

`prefect-kubernetes` is a collection of Prefect tasks, flows, and blocks enabling orchestration, observation and management of Kubernetes resources.

Jump to [examples](#example-usage).

## Resources

For more tips on how to use tasks and flows in a Collection, check out [Using Collections](https://docs.prefect.io/collections/usage/)!

### Installation
Install `prefect-kubernetes` with `pip`:
```bash
 pip install prefect-kubernetes
 ```

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

Then, to register [blocks](https://docs.prefect.io/ui/blocks/) on Prefect Cloud:

```bash
prefect block register -m prefect_kubernetes
```

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or saved through the UI.


### Example Usage

#### Use `with_options` to customize options on any existing task or flow

```python
from prefect_kubernetes.flows import run_namespaced_job

customized_run_namespaced_job = run_namespaced_job.with_options(
    name="My flow running a Kubernetes Job",
    retries=2,
    retry_delay_seconds=10,
) # this is now a new flow object that can be called
```

For more tips on how to use tasks and flows in a Collection, check out [Using Collections](https://docs.prefect.io/collections/usage/)!


#### Specify and run a Kubernetes Job from a yaml file

```python
from prefect_kubernetes.credentials import KubernetesCredentials
from prefect_kubernetes.flows import run_namespaced_job # this is a flow
from prefect_kubernetes.jobs import KubernetesJob

k8s_creds = KubernetesCredentials.load("k8s-creds")

job = KubernetesJob.from_yaml_file( # or create in the UI with a dict manifest
    credentials=k8s_creds,
    manifest_path="path/to/job.yaml",
)

job.save("my-k8s-job", overwrite=True)

if __name__ == "__main__":
    # run the flow
    run_namespaced_job(job)
```

#### Generate a resource-specific client from `KubernetesClusterConfig`

```python
# with minikube / docker desktop & a valid ~/.kube/config this should ~just work~
from prefect.blocks.kubernetes import KubernetesClusterConfig
from prefect_kubernetes.credentials import KubernetesCredentials

k8s_config = KubernetesClusterConfig.from_file('~/.kube/config')

k8s_credentials = KubernetesCredentials(cluster_config=k8s_config)

with k8s_credentials.get_client("core") as v1_core_client:
    for namespace in v1_core_client.list_namespace().items:
        print(namespace.metadata.name)
```


#### List jobs in a specific namespace

```python
from prefect import flow
from prefect_kubernetes.credentials import KubernetesCredentials
from prefect_kubernetes.jobs import list_namespaced_job

@flow
def kubernetes_orchestrator():
    v1_job_list = list_namespaced_job(
        kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
        namespace="my-namespace",
    )
```

#### Patch an existing deployment

```python
from kubernetes.client.models import V1Deployment

from prefect import flow
from prefect_kubernetes.credentials import KubernetesCredentials
from prefect_kubernetes.deployments import patch_namespaced_deployment
from prefect_kubernetes.utilities import convert_manifest_to_model

@flow
def kubernetes_orchestrator():

    v1_deployment_updates = convert_manifest_to_model(
        manifest="path/to/manifest.yaml",
        v1_model_name="V1Deployment",
    )

    v1_deployment = patch_namespaced_deployment(
        kubernetes_credentials=KubernetesCredentials.load("k8s-creds"),
        deployment_name="my-deployment",
        deployment_updates=v1_deployment_updates,
        namespace="my-namespace"
    )
```

## Feedback

If you encounter any bugs while using `prefect-kubernetes`, feel free to open an issue in the [prefect](https://github.com/PrefectHQ/prefect) repository.

If you have any questions or issues while using `prefect-kubernetes`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

## Contributing

If you'd like to help contribute to fix an issue or add a feature to `prefect-kubernetes`, please [propose changes through a pull request from a fork of the repository](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).
 
Here are the steps:
 
1. [Fork the repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#forking-a-repository)
2. [Clone the forked repository](https://docs.github.com/en/get-started/quickstart/fork-a-repo#cloning-your-forked-repository)
3. Install the repository and its dependencies:
```
 pip install -e ".[dev]"
```
4. Make desired changes
5. Add tests
6. Install `pre-commit` to perform quality checks prior to commit:
```
 pre-commit install
 ```
8. `git commit`, `git push`, and create a pull request