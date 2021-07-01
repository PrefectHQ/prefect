---
sidebarDepth: 2
editLink: false
---
# agent
---
### local
```
Manage Prefect Local agents.

Options:
  --help  Show this message and exit.

Commands:
  install  Generate a supervisord.conf file for a Local agent
  start    Start a local agent
```

### local install
```
Generate a supervisord.conf file for a Local agent

Options:
  -t, --token TEXT        A Prefect Cloud API token with RUNNER scope.
  -l, --label TEXT        Labels the agent will use to query for flow runs.
  -e, --env TEXT          Environment variables to set on each submitted flow
                          run.

  -p, --import-path TEXT  Import paths the local agent will add to all flow
                          runs.

  -f, --show-flow-logs    Display logging output from flows run by the agent.
  --help                  Show this message and exit.
```

### local start
```
Start a local agent

Options:
  -t, --token TEXT                A Prefect Cloud API token with RUNNER scope.
  -a, --api TEXT                  A Prefect API URL.
  --agent-config-id TEXT          An agent ID to link this agent instance with
  -n, --name TEXT                 A name to use for the agent
  -l, --label TEXT                Labels the agent will use to query for flow
                                  runs.

  -e, --env TEXT                  Environment variables to set on each
                                  submitted flow run.

  --max-polls INTEGER             Maximum number of times the agent should
                                  poll the Prefect API for flow runs. Default
                                  is no limit

  --agent-address TEXT            Address to serve internal api server at.
                                  Defaults to no server.

  --no-cloud-logs                 Turn off logging for all flows run through
                                  this agent. If not set, the Prefect config
                                  value will be used.

  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  The agent log level to use. Defaults to the
                                  value configured in your environment.

  -p, --import-path TEXT          Import paths the local agent will add to all
                                  flow runs.

  -f, --show-flow-logs            Display logging output from flows run by the
                                  agent.

  --storage-labels / --no-storage-labels
                                  Add all storage labels to the LocalAgent.
                                  DEPRECATED

  --hostname-label / --no-hostname-label
                                  Add hostname to the LocalAgent's labels
  --help                          Show this message and exit.
```

### docker
```
Manage Prefect Docker agents.

Options:
  --help  Show this message and exit.

Commands:
  start  Start a docker agent
```

### docker start
```
Start a docker agent

Options:
  -t, --token TEXT                A Prefect Cloud API token with RUNNER scope.
  -a, --api TEXT                  A Prefect API URL.
  --agent-config-id TEXT          An agent ID to link this agent instance with
  -n, --name TEXT                 A name to use for the agent
  -l, --label TEXT                Labels the agent will use to query for flow
                                  runs.

  -e, --env TEXT                  Environment variables to set on each
                                  submitted flow run.

  --max-polls INTEGER             Maximum number of times the agent should
                                  poll the Prefect API for flow runs. Default
                                  is no limit

  --agent-address TEXT            Address to serve internal api server at.
                                  Defaults to no server.

  --no-cloud-logs                 Turn off logging for all flows run through
                                  this agent. If not set, the Prefect config
                                  value will be used.

  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  The agent log level to use. Defaults to the
                                  value configured in your environment.

  -b, --base-url TEXT             Docker daemon base URL.
  --no-pull                       Disable pulling images in the agent
  -f, --show-flow-logs            Display logging output from flows run by the
                                  agent.

  --volume TEXT                   Host paths for Docker bind mount volumes
                                  attached to each Flow container. Can be
                                  provided multiple times to pass multiple
                                  volumes (e.g. `--volume /volume1 --volume
                                  /volume2`)

  --network TEXT                  Add containers to existing Docker networks.
                                  Can be provided multiple times to pass
                                  multiple networks (e.g. `--network network1
                                  --network network2`)

  --no-docker-interface           Disable the check of a Docker interface on
                                  this machine. Note: This is mostly relevant
                                  for some Docker-in-Docker setups that users
                                  may be running their agent with. DEPRECATED.

  --docker-client-timeout INTEGER
                                  The timeout to use for docker API calls,
                                  defaults to 60 seconds.

  --help                          Show this message and exit.
```

### kubernetes
```
Manage Prefect Kubernetes agents.

Options:
  --help  Show this message and exit.

Commands:
  install  Generate a supervisord.conf file for a Local agent
  start    Start a Kubernetes agent
```

### kubernetes install
```
Generate a supervisord.conf file for a Local agent

Options:
  -t, --token TEXT               A Prefect Cloud API token with RUNNER scope.
  -l, --label TEXT               Labels the agent will use to query for flow
                                 runs.

  -e, --env TEXT                 Environment variables to set on each
                                 submitted flow run.

  -a, --api TEXT                 A Prefect API URL.
  -n, --namespace TEXT           Agent namespace to launch workloads.
  -i, --image-pull-secrets TEXT  Name of image pull secrets to use for
                                 workloads.

  --rbac                         Enable default RBAC.
  --latest                       Use the latest Prefect image.
  --mem-request TEXT             Requested memory for Prefect init job.
  --mem-limit TEXT               Limit memory for Prefect init job.
  --cpu-request TEXT             Requested CPU for Prefect init job.
  --cpu-limit TEXT               Limit CPU for Prefect init job.
  --image-pull-policy TEXT       imagePullPolicy for Prefect init job
  --service-account-name TEXT    Name of Service Account for Prefect init job
  -b, --backend TEXT             Prefect backend to use for this agent.
  --help                         Show this message and exit.
```

### kubernetes start
```
Start a Kubernetes agent

Options:
  -t, --token TEXT                A Prefect Cloud API token with RUNNER scope.
  -a, --api TEXT                  A Prefect API URL.
  --agent-config-id TEXT          An agent ID to link this agent instance with
  -n, --name TEXT                 A name to use for the agent
  -l, --label TEXT                Labels the agent will use to query for flow
                                  runs.

  -e, --env TEXT                  Environment variables to set on each
                                  submitted flow run.

  --max-polls INTEGER             Maximum number of times the agent should
                                  poll the Prefect API for flow runs. Default
                                  is no limit

  --agent-address TEXT            Address to serve internal api server at.
                                  Defaults to no server.

  --no-cloud-logs                 Turn off logging for all flows run through
                                  this agent. If not set, the Prefect config
                                  value will be used.

  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  The agent log level to use. Defaults to the
                                  value configured in your environment.

  --namespace TEXT                Kubernetes namespace to deploy in. Defaults
                                  to `default`.

  --job-template TEXT             Path to a kubernetes job template to use
                                  instead of the default.

  --service-account-name TEXT     A default service account name to configure
                                  on started jobs.

  --image-pull-secrets TEXT       Default image pull secrets to configure on
                                  started jobs. Multiple values can be
                                  provided as a comma-separated list (e.g.
                                  `--image-pull-secrets VAL1,VAL2`)

  --disable-job-deletion          Turn off automatic deletion of finished jobs
                                  in the namespace.

  --help                          Show this message and exit.
```

### ecs
```
Manage Prefect ECS agents.

Options:
  --help  Show this message and exit.

Commands:
  start  Start an ECS agent
```

### ecs start
```
Start an ECS agent

Options:
  -t, --token TEXT                A Prefect Cloud API token with RUNNER scope.
  -a, --api TEXT                  A Prefect API URL.
  --agent-config-id TEXT          An agent ID to link this agent instance with
  -n, --name TEXT                 A name to use for the agent
  -l, --label TEXT                Labels the agent will use to query for flow
                                  runs.

  -e, --env TEXT                  Environment variables to set on each
                                  submitted flow run.

  --max-polls INTEGER             Maximum number of times the agent should
                                  poll the Prefect API for flow runs. Default
                                  is no limit

  --agent-address TEXT            Address to serve internal api server at.
                                  Defaults to no server.

  --no-cloud-logs                 Turn off logging for all flows run through
                                  this agent. If not set, the Prefect config
                                  value will be used.

  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  The agent log level to use. Defaults to the
                                  value configured in your environment.

  --cluster TEXT                  The cluster to use. If not provided, your
                                  default cluster will be used

  --launch-type [FARGATE|EC2]     The launch type to use, defaults to FARGATE
  --task-role-arn TEXT            The default task role ARN to use for ECS
                                  tasks started by this agent.

  --execution-role-arn TEXT       The default execution role ARN to use for
                                  ECS tasks started by this agent.

  --task-definition TEXT          Path to a task definition template to use
                                  when defining new tasks instead of the
                                  default.

  --run-task-kwargs TEXT          Path to a yaml file containing extra kwargs
                                  to pass to `run_task`

  --help                          Show this message and exit.
```

### fargate
```
Manage Prefect Fargate agents (DEPRECATED).

  The Fargate agent is deprecated, please transition to using the ECS agent
  instead.

Options:
  --help  Show this message and exit.

Commands:
  start  Start a Fargate agent (DEPRECATED) The Fargate agent is
         deprecated,...
```

### fargate start
```
Start a Fargate agent (DEPRECATED)

  The Fargate agent is deprecated, please transition to using the ECS agent
  instead.

Options:
  -t, --token TEXT                A Prefect Cloud API token with RUNNER scope.
  -a, --api TEXT                  A Prefect API URL.
  --agent-config-id TEXT          An agent ID to link this agent instance with
  -n, --name TEXT                 A name to use for the agent
  -l, --label TEXT                Labels the agent will use to query for flow
                                  runs.

  -e, --env TEXT                  Environment variables to set on each
                                  submitted flow run.

  --max-polls INTEGER             Maximum number of times the agent should
                                  poll the Prefect API for flow runs. Default
                                  is no limit

  --agent-address TEXT            Address to serve internal api server at.
                                  Defaults to no server.

  --no-cloud-logs                 Turn off logging for all flows run through
                                  this agent. If not set, the Prefect config
                                  value will be used.

  --log-level [DEBUG|INFO|WARNING|ERROR]
                                  The agent log level to use. Defaults to the
                                  value configured in your environment.

  --help                          Show this message and exit.
```
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>