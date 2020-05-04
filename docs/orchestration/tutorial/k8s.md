# Scaling Out with Kubernetes

::: warning Core server
In order to use this agent with Prefect Core's server the server's GraphQL API endpoint must be accessible.
:::

In previous tutorials we used the Local Agent and Docker Agent to execute flow runs on the current host. Now we will deploy our flow out to an existing Kubernetes Cluster.

## Running a Kubernetes Agent

In order to deploy your flow to Kubernetes the flow is required to have a Docker Storage with the image pushed to a registry that your Kubernetes cluster has access to.

```python
import prefect
from prefect import task, Flow
from prefect.environments.storage import Docker

@task
def hello_task():
    logger = prefect.context.get("logger")
    logger.info("Hello, Kubernetes!")

flow = Flow("hello-k8s", tasks=[hello_task])

flow.storage = Docker(registry_url="<your-registry.io>")

flow.register(project_name="Hello, World!")
```

The Kubernetes Agent can be run directly on your machine if you are currently authenticated with a Kubernetes cluster.

```bash
prefect agent start kubernetes
```

:::tip Runner Token <Badge text="Cloud"/>
This Kubernetes Agent will use the _RUNNER_ token stored in your environment but if you want to manually pass it a token you may do so with `--token <COPIED_RUNNER_TOKEN>`.
:::

The Kubernetes Agent will start listening for flow runs and when found it will create a [Kubernetes Job](https://kubernetes.io/docs/concepts/workloads/controllers/jobs-run-to-completion/) for each flow run.

:::warning RBAC for Job Management
The Kubernetes Agent requires [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) to work with jobs in its namespace.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: default
  name: prefect-agent-rbac
rules:
- apiGroups: ["batch", "extensions"]
  resources: ["jobs"]
  verbs: ["*"]

---

apiVersion: rbac.authorization.k8s.io/v1beta1
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

:::

## Installing an Agent on Kubernetes

For a high availability set up you should install the Kubernetes Agent into your cluster.

```bash
prefect agent install kubernetes -t <YOUR_RUNNER_TOKEN> --rbac | kubectl apply -f -
```

Once the Agent has been created on your cluster it create Jobs on that cluster for each flow run. For more information on the Kubernetes Agent visit the [documentation](/orchestration/agents/kubernetes.html).
