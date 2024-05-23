# prefect-kubernetes

`prefect-kubernetes` contains Prefect tasks, flows, and blocks enabling orchestration, observation and management of Kubernetes resources.

This library is most commonly used to installation with a Kubernetes worker. See the [Kubernetes guide](https://docs.prefect.io/latest/guides/deployment/kubernetes/) to learn how to create and run deployments in Kubernetes.
As noted in that guide, Prefect also provides a Helm chart for deploying a worker, a self-hosted server instance, and other resources to a Kubernetes cluster. See the [Prefect Helm chart](https://github.com/PrefectHQ/prefect-helm) for more information.

## Getting started

### Prerequisites

- [Prefect installed](https://docs.prefect.io/latest/getting-started/installation/) in a virtual environment.
- [Kubernetes installed](https://kubernetes.io/).

### Install `prefect-kubernetes`

<div class="terminal">
```bash
 pip install prefect-kubernetes
 ```
 </div>

### Register newly installed block types

Register the block types in the prefect-aws module to make them available for use.

<div class="terminal">
```bash
prefect block register -m prefect_kubernetes
```
</div>

## Examples

### Use `with_options` to customize options on an existing task or flow

```python
from prefect_kubernetes.flows import run_namespaced_job

customized_run_namespaced_job = run_namespaced_job.with_options(
    name="My flow running a Kubernetes Job",
    retries=2,
    retry_delay_seconds=10,
) # this is now a new flow object that can be called
```

### Specify and run a Kubernetes Job from a YAML file

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

### Generate a resource-specific client from `KubernetesClusterConfig`

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

### List jobs in a namespace

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

### Patch an existing Kubernetes deployment

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

For assistance using Kubernetes, consult the [Kubernetes documentation](https://kubernetes.io/).

Refer to the prefect-kubernetes API documentation linked in the sidebar to explore all the capabilities of the prefect-kubernetes library.
