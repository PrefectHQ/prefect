# Kubernetes Agent

The Kubernetes Agent is an agent designed to interact directly with a Kubernetes API server to run workflows as jobs on a Kubernetes cluster. This agent is intended to be deployed to a cluster where it uses in-cluster communication to create jobs; however it can also run by accessing whichever cluster is currently active in a kubeconfig.

[[toc]]

### Requirements

Running the Kubernetes Agent inside a cluster requires permission to create and list jobs. Consult the Kubernetes [RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) documentation to configure this if necessary.

:::tip GKE Permissions
If you are using GKE to quickly enable the correct permissions you can run:

```
kubectl create clusterrolebinding default-admin --clusterrole cluster-admin --serviceaccount=default:default
```

:::

### Usage

```
$ prefect agent start kubernetes

 ____            __           _        _                    _
|  _ \ _ __ ___ / _| ___  ___| |_     / \   __ _  ___ _ __ | |_
| |_) | '__/ _ \ |_ / _ \/ __| __|   / _ \ / _` |/ _ \ '_ \| __|
|  __/| | |  __/  _|  __/ (__| |_   / ___ \ (_| |  __/ | | | |_
|_|   |_|  \___|_|  \___|\___|\__| /_/   \_\__, |\___|_| |_|\__|
                                           |___/

2019-08-27 14:33:39,772 - agent - INFO - Starting KubernetesAgent
2019-08-27 14:33:39,772 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/
2019-08-27 14:33:40,932 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-08-27 14:33:40,932 - agent - INFO - Waiting for flow runs...
```

If running out-of-cluster (i.e. not on a pod) you may see the warning:

```
2019-09-01 14:33:38,749 - agent - WARNING - Service host/port is not set. Using out of cluster configuration option.
```

The Kubernetes Agent can be started either through the Prefect CLI or by importing the `KubernetesAgent` class from the core library.

::: tip Tokens
There are a few ways in which you can specify a `RUNNER` API token:

- command argument `prefect agent start kubernetes -t MY_TOKEN`
- environment variable `export PREFECT__CLOUD__AGENT__AUTH_TOKEN=MY_TOKEN`
- token will be used from `prefect.config.cloud.auth_token` if not provided from one of the two previous methods

:::

### Installation

The Prefect CLI provides commands for installing agents on their respective platforms.

```
$ prefect agent install --help
Usage: prefect agent install [OPTIONS] [NAME]

  Install an agent. Outputs configuration text which can be used to install
  on various platforms. The Prefect image version will default to your local
  `prefect.__version__`

  Arguments:
      name                        TEXT    The name of an agent to start (e.g. `kubernetes`)
                                          Defaults to `kubernetes`

  Options:
      --token, -t                 TEXT    A Prefect Cloud API token
      --api, -a                   TEXT    A Prefect Cloud API URL
      --namespace, -n             TEXT    Agent namespace to launch workloads
      --image-pull-secrets, -i    TEXT    Name of image pull secrets to use for workloads
      --resource-manager                  Enable resource manager on install
      --label, -l                 TEXT    Labels the agent will use to query for flow runs
                                          Multiple values supported e.g. `-l label1 -l label2`

Options:
  -h, --help  Show this message and exit.
```

Running the following command will install the Prefect Agent on your cluster:

```
$ prefect agent install kubernetes -t MY_TOKEN | kubectl apply -f -
```

The `install` command for Kubernetes will output a YAML deployment definition that can be applied to a cluster. You can view the output ahead of time by not piping the output into `kubectl apply`.

:::tip Namespace
By default, running `kubectl apply -f -` will apply the manifest against the _default_ namespace. To ensure the agent is deployed into your desired namespace it must be specified:

```
kubectl apply -n AGENT_NAMESPACE -f -
```

:::

Now you should be able to see the agent deployment created on your cluster:

```
$ kubectl get deploy
NAME            DESIRED   CURRENT   UP-TO-DATE   AVAILABLE   AGE
prefect-agent   1         1         1            0           2s

$ kubectl get pods
NAME                             READY   STATUS    RESTARTS   AGE
prefect-agent-845798bb59-s7wxg   1/1     Running   0          5s
```

You are now ready to run some flows!

#### Labels

To specify a set of labels for a Kubernetes Agent during install you may specify various `--label` arguments.

```
$ prefect agent install kubernetes -t MY_TOKEN --label dev --label staging
```

This will update the `PREFECT__CLOUD__AGENT__LABELS` environment variable on the Agent deployment YAML to include a string representation of a the list of labels. This means that providing the `dev` and `staging` labels above would be represented as:

```yaml
- name: PREFECT__CLOUD__AGENT__LABELS
  value: "['dev', 'staging']"
```

### Process

The Kubernetes Agent periodically polls for new flow runs to execute. When a flow run is retrieved from Prefect Cloud the agent checks to make sure that the flow was deployed with a Docker storage option. If so, the agent then creates a Kubernetes job using the `storage` attribute of that flow, and runs `prefect execute cloud-flow`.

When the job is found and submitted the logs of the agent should reflect that:

```
$ kubectl logs prefect-agent-845798bb59-s7wxg
2019-09-01 19:00:30,532 - agent - INFO - Starting KubernetesAgent
2019-09-01 19:00:30,533 - agent - INFO - Agent documentation can be found at https://docs.prefect.io/cloud/
2019-09-01 19:00:30,655 - agent - INFO - Agent successfully connected to Prefect Cloud
2019-09-01 19:00:30,733 - agent - INFO - Waiting for flow runs...
2019-09-01 19:01:08,835 - agent - INFO - Found 1 flow run(s) to submit for execution.
2019-09-01 19:01:09,158 - agent - INFO - Submitted 1 flow run(s) for execution.
```

The job and its respective pod should now be visible on the cluster:

```
$ kubectl get jobs
NAME                   COMPLETIONS   DURATION   AGE
prefect-job-39171cc4   0/1           4s         4s

$ kubectl get pods
NAME                             READY   STATUS              RESTARTS   AGE
prefect-agent-845798bb59-s7wxg   1/1     Running             0          61s
prefect-job-39171cc4-gffrp       0/1     ContainerCreating   0          9s
```

Once the flow has entered a finished state the pod's status should read `Completed`.

:::warning Resources
The current default resource usage of a prefect-job has a request and limit for CPU of `100m` and the agent limits itself to `128Mi` for memory and `100m` for CPU. Make sure your cluster has enough resources that it does not start to get clogged up with all of your flow runs. A more customizable Kubernetes environment is on the roadmap!
:::

### Resource Manager

Prefect is currently testing a feature called the Resource Manager alongside the Kubernetes agent. The Resource Manager is a small container that runs inside the agent's pod, responsible for cleaning up resources created from the orchestration of flow runs. For example: when a prefect-job is finished, the resource manager will delete the job and it's associated pods from the cluster. It checks every minute if there are prefect-jobs and pods that need to be cleaned up.

To install your agent with the resource manager run:

```
$ prefect agent install kubernetes -t MY_TOKEN --resource-manager | kubectl apply -f -
```
