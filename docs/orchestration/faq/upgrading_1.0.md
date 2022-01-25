# Upgrading to Prefect 1.0

Prefect 1.0 includes some important changes that may require updates to your flow and task definitions. 

Most significant: support has been removed for some features previously marked as deprecated. This means flows using deprecated features may encounter errors rather than warnings.

The following sections describe changes you should be aware of for making sure your flows work as expected with Prefect 1.0.

[[toc]]

## API keys replace authentication tokens

[API keys](/orchestration/concepts/api_keys.html) replace authentication tokens to authenticate users and service accounts with the Prefect Cloud API. Existing authentication tokens will be ignored.

See [Removing API tokens](/orchestration/concepts/api_keys.html#removing-api-tokens) to learn how to remove old tokens from your environment. See [Using API keys with older versions of Prefect](/orchestration/concepts/api_keys.html#using-api-keys-with-older-versions-of-prefect) for details about how you can use API keys in place of tokens in certain situations (such as a VM or container built with an older version of Prefect).

The Prefect CLI commands `create-token`, `revoke-token`, and `list-tokens` have been removed.

The `prefect auth login` and `prefect auth logout` commands now use API keys. Previously, logging out with an API token would just reset your tenant and access token, but leave the API token on disk. Now, we retain that behavior the first time the command is called, but if you call it a second time, we delete the API token. This allows users to easily remove their API token in favor of an API key.

Agents will use an available API key as detected by the Client, but will no longer detect tokens. If you have logged in locally, you may start any kind of agent and the agent will use your API key to query for flow runs, then pass the API key to the flow run for execution as well.

When using the non-default tenant associated with an API key, set the tenant on the flow run job or the flow run will instantiate a client with the wrong tenant ID to report to Cloud. If the default tenant or a token is being used, this environment variable is just left blank.

```bash
# install agent, specifying API key and tenant
$ prefect agent [agent-type] install --key [api-key] --tenant-id [tenant-id]

# start agent, specifying API key and tenant
$ prefect agent [agent-type] start --key [api-key] --tenant-id [tenant-id]
```

## Support for environments

Flow environments, deprecated since Prefect 0.14.0, have been removed completely. Use `RunConfig` objects to define where and how a flow run should be executed as described in [Run Configuration](/orchestration/flow_config/run_configs.html).

If you do not have `flow.environment` configured explicitly on your flow, there is no impact on your flows and no migration steps are needed.

If you still have environment configurations, the topic [Upgrading from Prefect < 0.14.0](/orchestration/flow_config/upgrade.html) provides detailed instructions for migrating to `RunConfig`.

## Registering and running flows with the CLI

The Prefect CLI commands to register and run flows have been revised, changing the syntax and adding new functionality.

### Registering flows

The `prefect register` command replace the `prefect register flow` command to [Register a flow](/orchestration/getting-started/registering-and-running-a-flow.html#register-a-flow) with the CLI. 

- Allows registering multiple flows in a single call. Flows can be specified by `--path` (path to a file or directory containing flows) or by `--module` (an importable Python module containing flows). Both options can be specified multiple times in a single call for more flexibility.
- A `--name` flag can be used to only register flows with a specific name (or names). If unspecified, all flows found are registered.
- By default, a flow will only be re-registered if it is *structurally different* than the existing version. This means that small edits to the source of tasks won't require re-registration, and the CLI will automatically detect this to avoid needlessly bumping the version. This can be disabled by passing in `--force`.
- A `--watch` flag enables watching for changes in a directory, path, or module and re-registering flows if a change is detected. This can be used during development to automatically re-register your flows on save (as needed), or as part of a deployment for users who want to watch and auto-update flows from a specific directory.

These features simplify auto-registering flows from within CI. For example, with GitHub actions you might add the following step to your CI workflow to auto-register all flows in a `flows/` directory on merge.

```yaml
- name: Register Flows
  if: github.ref == 'refs/heads/master'
  run: prefect register flows --project testing --path flows
```

The changes in flow registration require Prefect Server 2021.09.02 or later. Prefect Server will need to be upgraded before flows can be registered from this version.

### Running flows

The `prefect run` replaces the `prefect run flow` command to run a flow from the CLI.

`prefect run` can run flows locally without the backend (Prefect Server or Prefect Cloud), or with the backend by submitting to an agent. It takes many options for lookup including a Python import name, a file path, the flow ID, the flow group ID, flow name, or project name. The flow run state change and log display has been entirely rewritten to be nice looking. I've also moved all of the flow watching functionality into a method so any flow run can be easily watched.

`prefect run` supports the following options:

| Option | Description |
| --- | --- |
| -i, --id           | The UUID of a flow or flow group to run. If a flow group id is given, the latest flow id will be used for the run. |
| --project          | The name of the Prefect project containing the flow to run. |
| -p, --path         | The path to a file containing the flow to run. |
| -m, --module       | The python module name containing the flow to run. |
| -n, --name         | The name of a flow to run from the specified file/module/project. If the source contains multiple flows, this must be provided. |
| --label            | A label to add to the flow run. May be passed multiple times to specify multiple labels. If not passed, the labels from the flow group will be used. |
| --run-name         | A name to assign to the flow run. |
| --con              | A key, value pair (key=value) specifying a flow con variable. The value will be interpreted as JSON. May be passed multiple times to specify multiple con values. Nested values may be set by passing a dict. |
| --param            | A key, value pair (key=value) specifying a flow parameter. The value will be interpreted as JSON. May be passed multiple times to specify multiple parameter values. |
| --log-level        | The log level to set for the flow run. If passed, the level must be a valid Python logging level name. If this option is not passed, the default level for the flow will be used. Valid values include DEBUG, INFO, WARNING, ERROR, or CRITICAL. |
| --param-file       | The path to a JSON file containing parameter keys and values. Any parameters passed with `--param` will take precedence over these values. |
| <span class="no-wrap" style="white-space:nowrap;">--idempotency-key</span>  | A key to prevent duplicate flow runs. If a flow run has already been started with the provided value, the command will display information for the existing run. If using `--execute`, duplicate flow runs will exit with an error. If not using the backing API, this flag has no effect. |
| --execute          | Execute the flow run in-process without an agent. If this process exits, the flow run will be marked as 'Failed'. |
| -s, --schedule     | Execute the flow run according to the schedule attached to the flow. If this flag is set, this command will wait between scheduled flow runs. If the flow has no schedule, this flag will be ignored. If used with a non-local run, an exception will be thrown. |
| -q, --quiet        | Disable verbose messaging about the flow run and just print the flow run ID. |
| --no-logs          | Disable streaming logs from the flow run to this terminal. Only state changes will be displayed. Only applicable when `--watch` is set. |
| -w, --watch        | Wait for the flow run to finish executing and display status information. |

For example, run a flow in a script locally:

```bash
$ prefect run -p hello-world.py
```

Run a flow with a non-default parameter locally:

```bash
$ prefect run -m prefect.hello_world --param name=Marvin
```

Run a registered flow with the backend with custom labels:

```bash
$ prefect run -n "hello-world" --label example --label hello
```

Run a registered flow and execute locally without an agent

```bash
$ prefect run -n "hello-world" --execute
```

## Imports have moved

Imports for some Prefect modules have moved:

- Artifacts functions now imported from `prefect.backend.artifacts`.
- `Parameter` now imported from `prefect.Parameter` instead of `prefect.core.tasks`.
- Exceptions now imported from `prefect.exceptions` instead of `prefect.utilities.exceptions`.
- Executors now imported from `prefect.executors` instead of `prefect.engine.executors`. 

## iCal recurrence rules schedules

Prefect now supports rich recurrence rule scheduling following the iCal RRules standard and `dateutil` `rrule` module. This feature does not impact existing schedules using interval clocks, cron clocks, and so on, but provides convenient, new syntax for creating repetitive schedules. See [Recurrence Rule Clocks](/core/concepts/schedules.html#recurrence-rule-clocks) for details.

## Drop support for Python 3.6

Prefect 1.0 drops explicit support for Python 3.6. The minimum version for test and build is Python 3.7. 

## Prefect server services local by default

Services run by prefect server cli are now local by default (listen to localhost instead of 0.0.0.0); use `--expose` if you want to connect from a remote location 

Relevant PRs:

- 4821 (0.15.5)
- 5156
- 5182

## Additional changes

Prefect 1.0 includes a number of additional minor changes:

- The AWS Fargate agent has been removed. Use the [ECS agent](/orchestration/agents/ecs.html) instead to deploy flow runs as AWS ECS tasks on either EC2 or Fargate.
- For the [Docker agent](/orchestration/agents/docker.html) the deprecated `DockerAgent(docker_interface=...)` argument has been removed and will now raise an exception if passed.
- The `log_to_cloud` setting is now ignored. Use `send_flow_run_logs` instead. See [Logging with a backend](/core/idioms/logging.html#logging-with-a-backend) for details.