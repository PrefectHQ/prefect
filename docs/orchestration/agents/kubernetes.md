# Kubernetes Agent

The Kubernetes Agent deploys flow runs as [Kubernetes
Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/). It can
be run both in-cluster (recommended for production deployments) as well as
external to the cluster.

[[toc]]

## Requirements

If running locally, note that the required dependencies for the Kubernetes
Agent aren't [installed by default](/core/getting_started/installation.md). If
you're a `pip` user you'll need to add the `kubernetes` extra. Likewise, with
`conda` you'll need to install the extra `kubernetes` package:

:::: tabs
::: tab Pip

```bash
pip install prefect[kubernetes]
```

:::
::: tab Conda

```bash
conda install -c conda-forge prefect python-kubernetes
```

:::
::::

If you're deploying the Kubernetes Agent in-cluster, you won't need to worry
about this.

!!! warning Prefect Server
    In order to use this agent with Prefect Server the server's GraphQL API
    endpoint must be accessible. This _may_ require changes to your Prefect Server
    deployment and/or [configuring the Prefect API
    address](./overview.md#prefect-api-address) on the agent.
:::

## Flow Configuration

The Kubernetes Agent will deploy flows using either a
[UniversalRun](/orchestration/flow_config/run_configs.md#universalrun) (the
default) or [KubernetesRun](/orchestration/flow_config/run_configs.md#kubernetesrun)
`run_config`. Using a `KubernetesRun` object lets you customize the deployment
environment for a flow (exposing `env`, `image`, `cpu_limit`, etc...):

```python
from prefect.run_configs import KubernetesRun

# Configure extra environment variables for this flow,
# and set a custom image
flow.run_config = KubernetesRun(
    env={"SOME_VAR": "VALUE"},
    image="my-custom-image"
)
```

See the [KubernetesRun](/orchestration/flow_config/run_configs.md#kubernetesrun)
documentation for more information.

## Agent Configuration

The Kubernetes agent can be started from the Prefect CLI as

```bash
prefect agent kubernetes start
```

!!! tip API Keys <Badge text="Cloud"/>
  When using Prefect Cloud, this will require a service account API key, see
  [here](./overview.md#api_keys) for more information.
:::

Below we cover a few common configuration options, see the [CLI
docs](/api/latest/cli/agent.md#kubernetes-start) for a full list of options.

### Authentication

If running external to the cluster, you'll need to ensure your active
[kubeconfig](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
is valid and for the proper cluster.

When running in-cluster, the Agent pod will need the proper RBAC credentials.
This is covered in more detail [below](#running-in-cluster).

### Namespace

By default the agent will deploy flow run jobs into the `default` namespace.
You can use the `--namespace` option to change this:

```bash
prefect agent kubernetes start --namespace my-namespace
```

### Service Account

You can use the `--service-account-name` option to configure a [service
account](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/)
to use for all Jobs deployed by the agent.

```bash
prefect agent kubernetes start --service-account-name my-account
```

Flows can override this agent default by passing the `service_account_name` option to
their respective
[KubernetesRun](/orchestration/flow_config/run_configs.md#kubernetesrun)
`run_config`.

### Image Pull Secrets

Likewise, the `--image-pull-secrets` option can be used to configure [image
pull
secrets](https://kubernetes.io/docs/concepts/containers/images/#specifying-imagepullsecrets-on-a-pod)
for all Jobs deployed by the agent. Multiple secrets can be provided as a
comma-separated list. Note that the secrets must already exist within the same
`namespace` as the agent.

```bash
prefect agent kubernetes start --image-pull-secrets secret-1,secret-2
```

Flows can override this agent default by passing the `image_pull_secrets` option to
their respective
[KubernetesRun](/orchestration/flow_config/run_configs.md#kubernetesrun)
`run_config`.

### Custom Job Template

For deeper customization of the Kubernetes Job created by the agent, you may
want to make use of a custom job template. This template can either be
configured per-flow (on the
[KubernetesRun](/orchestration/flow_config/run_configs.md#kubernetesrun)
`run_config`), or on the Agent as a default for flows that don't provide their
own template.

For reference, the default template packaged with Prefect can be found
[here](https://github.com/PrefectHQ/prefect/blob/master/src/prefect/agent/kubernetes/job_template.yaml).

To provide your own job template, you can use the `--job-template` flag. This
takes a path to a job template YAML file. The path can be local to the agent,
or stored in cloud storage on either GCS or S3 (note that in this case, the
agent will need credentials for S3/GCS access).

```bash
# Using a local file
prefect agent kubernetes start --job-template /path/to/my_template.yaml

# Stored on S3
prefect agent kubernetes start --job-template s3://bucket/path/to/my_template.yaml
```

## Running In-Cluster

For production deployments, we recommend running the Kubernetes Agent inside
the Kubernetes Cluster as a
[Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/).
This helps ensure your agent is active and healthy.

To make this easier, the Prefect CLI provides a command for generating an
example Kubernetes Manifest you can use for creating such a deployment.

```bash
prefect agent kubernetes install
```

The `install` command accepts many of the same options as the `start` command -
see the [CLI documentation](/api/latest/cli/agent.md#kubernetes-install) for
all available options.

The generated manifest can be piped to `kubectl apply`, or manually edited to
further customize the deployment.

```bash
prefect agent kubernetes install -k API_KEY | kubectl apply --namespace=my-namespace -f -
```

Once created, you should be able to see the agent deployment running in your
cluster:

```
$ kubectl get deploy
NAME            DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
prefect-agent   1         1         1            0           2s

$ kubectl get pods
NAME                             READY   STATUS    RESTARTS   AGE
prefect-agent-845798bb59-s7wxg   1/1     Running   0          5s
```

### RBAC

The Kubernetes Agent requires certain
[RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
permissions to work with jobs in its namespace. The proper RBAC configuration
can be generated by providing the `--rbac` flag to `prefect agent kubernetes install`- for reference we provide it below as well.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: prefect-agent-rbac
rules:
  - apiGroups: ['batch', 'extensions']
    resources: ['jobs']
    verbs: ['*']
  - apiGroups: ['']
    resources: ['events', 'pods']
    verbs: ['*']
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  namespace: default
  name: prefect-agent-rbac
subjects:
  - kind: ServiceAccount
    name: default
roleRef:
  kind: Role
  name: prefect-agent-rbac
  apiGroup: rbac.authorization.k8s.io
```

### Additional Permissions

If you are using Amazon EKS for your kubernetes deployment and you need S3
access, note that S3 is not accessible by default to Amazon EKS. To enable S3
access by your kubernetes cluster on EKS, add the necessary permissions
(AmazonS3FullAccess or AmazonS3ReadOnlyAccess) directly to the NodeInstanceRole
used by aws-auth-cm.yaml after launching worker nodes and before applying
aws-auth-cm.yaml with kubectl.
