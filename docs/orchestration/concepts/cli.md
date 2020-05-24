---
sidebarDepth: 2
---

# CLI

In conjunction with both the GraphQL API and the UI, Prefect offers a fully-integrated CLI for working with the Prefect API. Using Prefect's GraphQL API as the backbone for communicating with the back end, we have designed the CLI to operate as a wrapper for GraphQL queries and mutations.

In this current state the Prefect CLI functions mainly as a way to read Prefect API metadata as well as a lightweight way to perform some more functional operations such as running a flow that was registered.

::: warning Commands subject to change!
The CLI is being built to comply with user demands on what is deemed useful. Therefore the names and outputs of some of these are subject to change during the rollout process.
:::

## Interacting with the CLI

<!-- TODO: Update with new CLI changes -->

Once you have Prefect installed (either through `pip` or `conda`) you may begin working with the CLI directly in your terminal. To see the CLI run `prefect` from the command line and you should see an output similar to the one below:

```
$ prefect
Usage: prefect [OPTIONS] COMMAND [ARGS]...

  The Prefect CLI for creating, managing, and inspecting your flows.

  Note: a Prefect Cloud API token is required for all Cloud related commands. If a token
  is not set then run `prefect auth login` to set it.

  Query Commands:
      get         List high-level object information
      describe    Retrieve detailed object descriptions

  Action Commands:
      agent       Manage agents
      create      Create objects
      execute     Execute a flow's environment
      run         Run a flow

  Setup Commands:
      auth        Handle Prefect Cloud authorization

  Miscellaneous Commands:
      version     Get your current Prefect version
      config      Output your Prefect config

Options:
  -h, --help  Show this message and exit.
```

From this help output you can see that the commands are broken into the categories `query`, `execution`, `setup`, and `miscellaneous`. Each category has groups (e.g. `get`, `describe`) and each group has commands for interacting with particular Prefect objects (e.g. `prefect get flows`). Every group and command is also provided with help documentation that can be accessed through `--help` or `-h`.

## Query Commands

### get

`get` is used to retrieve high level information about Prefect Cloud objects. Currently CLI users can get `flows`, `flow-runs`, `projects`, `tasks`, and `logs`.

#### get flows

Running `prefect get flows` without any extra arguments will output a table of your current flows.

```
$ prefect get flows
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   2         New-Proj       22 hours ago
my-flow     1         Demo           2 weeks ago
```

To get more specific flow information you can optionally provide values for `--name`, `--version`, `--project` that will filter the table that is shown.

```
$ prefect get flows --name my-flow
NAME        VERSION   PROJECT NAME   AGE
my-flow     1         Demo           2 weeks ago
```

```
$ prefect get flows --project New-Proj
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   2         New-Proj       22 hours ago
```

```
$ prefect get flows --project New-Proj --version 1
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   1         New-Proj       1 month ago
```

By default this command shows the most recent version of a flow. To see all versions use the `--all-versions` flag.

```
$ prefect get flows --all-versions
NAME        VERSION   PROJECT NAME   AGE
Test-Flow   2         New-Proj       22 hours ago
Test-Flow   1         New-Proj       1 month ago
my-flow     1         Demo           2 weeks ago
```

#### get flow-runs

Running `prefect get flow-runs` without any extra arguments will output a table of your most recent flow runs (default is the 10 most recent).

```
$ prefect get flow-runs
NAME                FLOW NAME    STATE      AGE             START TIME           DURATION
archetypal-terrier  my-flow      Scheduled  2 minutes ago
turquoise-gazelle   my-flow      Success    2 weeks ago     2019-07-25 18:30:04  00:00:02
agate-parakeet      my-flow      Success    2 weeks ago     2019-07-25 17:58:29  00:00:02
wonderful-boa       my-flow      Success    2 weeks ago     2019-07-25 16:37:34  00:00:02
pastoral-auk        my-flow      Success    2 weeks ago     2019-07-25 16:04:43  00:00:02
nebulous-lyrebird   my-flow      Success    2 weeks ago     2019-07-25 14:41:35  00:00:02
mighty-jellyfish    my-flow      Success    2 weeks ago     2019-07-25 14:41:30  00:00:02
coral-lemming       my-flow      Success    2 weeks ago     2019-07-25 14:40:41  00:00:02
magenta-oxpecker    my-flow      Success    2 weeks ago     2019-07-25 14:37:55  00:00:02
rapid-gibbon        my-flow      Success    2 weeks ago     2019-07-25 14:36:25  00:00:02
```

::: warning Prettier Output
In each output the `DURATION` column timestamp was trimmed in order to make the tables fit better on this page.
:::

To increase the amount retrieved you can specify a `--limit` integer. Similar to other get commands `get flow-runs` supports filtering of `--flow` and `--project` where a certain flow name or project name can be provided to filter the table.

There is an extra argument to filter only for flow runs that have started (either are currently running or have entered a finished state) by using the `--started` flag. In the output below notice that the flow run with the name `archetypal-terrier` is missing because it has not started.

```
$ prefect get flow-runs --started
NAME                FLOW NAME    STATE      AGE             START TIME           DURATION
turquoise-gazelle   my-flow      Success    2 weeks ago     2019-07-25 18:30:04  00:00:02
agate-parakeet      my-flow      Success    2 weeks ago     2019-07-25 17:58:29  00:00:02
wonderful-boa       my-flow      Success    2 weeks ago     2019-07-25 16:37:34  00:00:02
pastoral-auk        my-flow      Success    2 weeks ago     2019-07-25 16:04:43  00:00:02
nebulous-lyrebird   my-flow      Success    2 weeks ago     2019-07-25 14:41:35  00:00:02
mighty-jellyfish    my-flow      Success    2 weeks ago     2019-07-25 14:41:30  00:00:02
coral-lemming       my-flow      Success    2 weeks ago     2019-07-25 14:40:41  00:00:02
magenta-oxpecker    my-flow      Success    2 weeks ago     2019-07-25 14:37:55  00:00:02
rapid-gibbon        my-flow      Success    2 weeks ago     2019-07-25 14:36:25  00:00:02
```

#### get projects

Running `prefect get projects` without any extra arguments will output a table of your projects. Optionally you can specify `--name` to retrieve a specific project.

```
$ prefect get projects
NAME                   FLOW COUNT    AGE          DESCRIPTION
Demo                   1             2 weeks ago
```

#### get tasks

Running `prefect get tasks` without any extra arguments will output a table of your current tasks (default is the 10 most recent).

```
$ prefect get tasks
NAME          FLOW NAME   FLOW VERSION   AGE          MAPPED   TYPE
first_task    Test-Flow   1              5 days ago   False    prefect.tasks.core.function.FunctionTask
second_task   Test-Flow   1              5 days ago   True     prefect.tasks.core.function.FunctionTask
my_task       my-flow     1              2 weeks ago  False    prefect.tasks.core.function.FunctionTask
```

To increase the amount retrieved you can specify a `--limit` integer. Similar to other get commands `get tasks` supports filtering with `--name` for the name of a task, `--flow-name` for the name of a flow, `--flow-version` for the version of a flow, and `--project` for a project name.

#### get logs

Running `prefect get logs` requires that a flow run name is provided through `--name`. It outputs a table of logs from that flow run.

```
$ prefect get logs --name fearless-hyrax
TIMESTAMP                         LEVEL    MESSAGE
2019-07-17T23:37:22.816988+00:00  INFO     Beginning Flow run for 'my-flow'
2019-07-17T23:37:23.214365+00:00  INFO     Starting flow run.
2019-07-17T23:37:23.365119+00:00  INFO     Flow 'my-flow': Handling state change from Scheduled to Running
2019-07-17T23:37:23.915298+00:00  INFO     Task 'my_task': Starting task run...
2019-07-17T23:37:24.113271+00:00  INFO     Task 'my_task': Handling state change from Pending to Running
2019-07-17T23:37:24.666+00:00     INFO     Task 'my_task': Calling task.run() method...
2019-07-17T23:37:24.813664+00:00  INFO     Task 'my_task': Handling state change from Running to Success
2019-07-17T23:37:25.15329+00:00   INFO     Task 'my_task': finished task run for task with final state: 'Success'
2019-07-17T23:37:25.351535+00:00  INFO     Flow run SUCCESS: all reference tasks succeeded
2019-07-17T23:37:25.514397+00:00  INFO     Flow 'my-flow': Handling state change from Running to Success
```

To retrieve more information about each of the logs in JSON pass the `--info` flag to the command.

```
$ prefect get logs --name fearless-hyrax --info
{
    "msg": "Beginning Flow run for 'my-flow'",
    "args": [],
    "name": "prefect.CloudFlowRunner",
    "msecs": 816.9882297515869,
    "lineno": 224,
    "module": "flow_runner",
    "thread": 140362462062400,
    "asctime": "2019-07-17 23:37:22,816",
    "created": 1563406642.8169882,
    "levelno": 20,
    "message": "Beginning Flow run for 'my-flow'",
    "process": 6,
    "exc_info": null,
    "exc_text": null,
    "filename": "flow_runner.py",
    "funcName": "run",
    "pathname": "/usr/local/lib/python3.6/site-packages/prefect/engine/flow_runner.py",
    "levelname": "INFO",
    "stack_info": null,
    "threadName": "MainThread",
    "processName": "MainProcess",
    "relativeCreated": 7002.268075942993
}
etc...
```

### describe

`describe` is used to retrieve descriptive metadata information about Prefect Cloud objects. Currently CLI users can describe `flows`, `flow-runs`, and `tasks`.

#### describe flows

Running `prefect describe flows` requires that a flow name be provided through the `--name` option. This outputs flow descriptive metadata.

```
$ prefect describe flows --name my-flow
{
    "name": "my-flow",
    "version": 1,
    "project": {
        "name": "Demo"
    },
    "created": "2019-07-25T14:23:21.704585+00:00",
    "description": null,
    "parameters": [],
    "archived": false,
    "storage": {
        "type": "Docker",
        "flows": {
            "my-flow": "/root/.prefect/my-flow.prefect"
        },
        "image_tag": "9b444406-355b-4d32-832e-77ddc21d2073",
        "image_name": "my-flow",
        "__version__": "0.6.0",
        "registry_url": "gcr.io/my-registry/",
        "prefect_version": "master"
    },
    "environment": {
        "type": "RemoteEnvironment",
        "executor": "prefect.engine.executors.SynchronousExecutor",
        "__version__": "0.6.1",
        "executor_kwargs": {}
    }
}
```

This defaults to the most recent version of a flow and to describe past versions use the `--version` option. You can also specify the project name that a flow belongs to with `--project` (often used if you have multiple flows with the same name in various projects).

#### describe flow-runs

Running `prefect describe flow-runs` requires that a flow run name be provided through the `--name` option. This outputs flow run descriptive metadata.

```
$ prefect describe flow-runs --name turquoise-gazelle
{
    "name": "turquoise-gazelle",
    "flow": {
        "name": "my-flow"
    },
    "created": "2019-07-25T18:29:49.926177+00:00",
    "parameters": {},
    "auto_scheduled": false,
    "scheduled_start_time": "2019-07-25T18:29:49.908098+00:00",
    "start_time": "2019-07-25T18:30:04.201221+00:00",
    "end_time": "2019-07-25T18:30:06.603138+00:00",
    "duration": "00:00:02.401917",
    "heartbeat": "2019-07-25T18:30:06.603138+00:00",
    "serialized_state": {
        "type": "Success",
        "_result": {
            "type": "NoResultType",
            "__version__": "0.6.0"
        },
        "message": "All reference tasks succeeded.",
        "__version__": "0.6.1"
    }
}
```

#### describe tasks

Running `prefect describe tasks` requires that a flow name be provided through the `--name` option. This outputs task descriptive metadata that correspond to a flow.

```
$ prefect describe tasks --name my-flow
{
    "name": "my_task",
    "created": "2019-07-25T14:23:21.704585+00:00",
    "slug": "2fe4be08-5ac6-4aea-953b-cb9394596145",
    "description": null,
    "type": "prefect.tasks.core.function.FunctionTask",
    "max_retries": 0,
    "retry_delay": null,
    "mapped": false
}
```

This defaults to the most recent version of a flow and to describe tasks for past versions use the `--version` option. You can also specify the project name that a flow belongs to with `--project` (often used if you have multiple flows with the same name in various projects).

## Action Commands

### agent

For more information regarding Prefect Agents refer to the [agent documentation](https://docs.prefect.io/orchestration/agents/overview.html).

### create

#### create project

Running `prefect create project PROJECT_NAME` will create a project in Prefect Cloud with the given name. You can also specify a project description with `--description`.

```
$ prefect create project "MY PROJECT" -d "description here"
MY PROJECT created
```

### execute

#### execute cloud-flow

::: warning Not Useful for Local Execution
This command executes a flow's environment in the context of Prefect Cloud and runs during Cloud execution so it is not meant for local use. Other `execute` commands may be added in the future.
:::

### run

#### run cloud

Running this command requires that a flow name (`--name`) and project (`--project`) is specified in order to create a flow run for that particular flow in Prefect Cloud.

```
$ prefect run cloud --name my-flow --project Demo
Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3ddfd-411c-4d99-bb2a-f64a6dea87f9
```

There is an optional `--version` argument that can be passed in with the command to run any version of a flow that exists in Prefect Cloud.

This command also supports two live output options, `--watch` and `--logs`. Using `--watch` will live update the command line with the flow run's current state until it reaches a finished state and `--logs` will update the command line with live logs from the flow run. These two flags currently cannot be used at the same time in a single call.

Live updating output with `--watch`:

```
$ prefect run cloud --name my-flow --project Demo --watch
Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3ddfd-411c-4d99-bb2a-f64a6dea87f9
Scheduled -> Submitted -> Running -> Success
```

Live updating output with `--logs`:

```
$ prefect run cloud --name my-flow --project Demo --logs
Flow Run: https://cloud.prefect.io/myslug/flow-run/2ba3ddfd-411c-4d99-bb2a-f64a6dea87f9
TIMESTAMP                         LEVEL    MESSAGE
2019-07-17T23:37:22.816988+00:00  INFO     Beginning Flow run for 'my-flow'
2019-07-17T23:37:23.214365+00:00  INFO     Starting flow run.
2019-07-17T23:37:23.365119+00:00  INFO     Flow 'my-flow': Handling state change from Scheduled to Running
2019-07-17T23:37:23.915298+00:00  INFO     Task 'my_task': Starting task run...
2019-07-17T23:37:24.113271+00:00  INFO     Task 'my_task': Handling state change from Pending to Running
2019-07-17T23:37:24.666+00:00     INFO     Task 'my_task': Calling task.run() method...
2019-07-17T23:37:24.813664+00:00  INFO     Task 'my_task': Handling state change from Running to Success
2019-07-17T23:37:25.15329+00:00   INFO     Task 'my_task': finished task run for task with final state: 'Success'
2019-07-17T23:37:25.351535+00:00  INFO     Flow run SUCCESS: all reference tasks succeeded
2019-07-17T23:37:25.514397+00:00  INFO     Flow 'my-flow': Handling state change from Running to Success
```

## Setup Commands

### auth

`auth` is a group of commands that handle authentication related configuration with Prefect Cloud.

::: warning Config
Having an API token set as a config value prior to using auth CLI commands, either in your config.toml or as an environment variable, will cause all auth commands to abort on use.
:::

#### auth login

Running `prefect auth login` requires that a Prefect Cloud API token be provided and when executed the API token is used to login to Prefect Cloud.

```
$ prefect auth login --token $MY_TOKEN
Login successful
```

If the API token is not valid then you should see:

```
$ prefect auth login --token BAD_TOKEN
Error attempting to use Prefect API token BAD_TOKEN
```

#### auth logout

Running `prefect auth logout` will log you out of your active tenant (if you are logged in)

```
$ prefect auth logout
Are you sure you want to log out of Prefect Cloud? (y/N) Y
Logged out from tenant PREVIOUS_ACTIVE_TENANT_ID
```

If there is no current active tenant then you should see:

```
$ prefect auth logout
Are you sure you want to log out of Prefect Cloud? (y/N) Y
No tenant currently active
```

#### auth list-tenants

Running `prefect auth list-tenants` will output all of the tenants that you have access to use.

```
$ prefect auth list-tenants
NAME                        SLUG                        ID
Test Person                 test-person                 816sghf2-4d51-4338-a333-1771gns7614d
test@prefect.io's Account   test-prefect-io-s-account   1971hs9f-e8ha-4a33-8c33-64512gds86g1  *
```

#### auth switch-tenants

Running `prefect auth switch-tenants --id TENANT_ID --slug TENANT_SLUG` will switch your active tenants. Either the tenant ID or the tenant slug needs to be provided.

```
$ prefect auth switch-tenants --slug test-person
Tenant switched
```

If you are unable to switch tenants for various reasons (bad id, bad slug, not providing either) then you should see:

```
$ prefect auth switch-tenants --slug test-person
Unable to switch tenant
```

#### auth create-token

Running `prefect auth create-token --name MY_TOKEN --scope RUNNER` will generate a Prefect Cloud API token and output it to stdout. For more information on API tokens go [here](./api.html).

```
$ prefect auth create-token -n MyToken -r RUNNER
...token output...
```

If you are unable to create an API token then you should see:

```
$ prefect auth create-token -n MyToken -r RUNNER
Issue creating API token
```

#### auth revoke-token

Running `prefect auth revoke-token --id TOKEN_ID` will revoke API tokens in Prefect Cloud.

```
$ prefect auth revoke-token --id TOKEN_ID
Token successfully revoked
```

If the token is not found then you should see:

```
$ prefect auth revoke-token --id TOKEN_ID
Unable to revoke token with ID TOKEN_ID
```

#### auth list-tokens

Running `prefect auth list-tokens` will list your available API tokens in Prefect Cloud. Note: only the name and ID of the token will be shown, not the actual token.

```
$ prefect auth list-tokens
NAME        ID
My_Token    87gh22f4-333c-47fc-ae8f-0b61ghu811c3
```

If you are unable to list API tokens then you should see:

```
$ prefect auth list-tokens
Unable to list API tokens
```

## Miscellaneous Commands

`prefect version` outputs the current version of Prefect you are using:

```
$ prefect version
0.6.1
```

`prefect config` outputs your current Prefect config that will be loaded:

```
$ prefect config
...config output...
```
