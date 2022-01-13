# Upgrading to Prefect 1.0

## Drop client handling of authentication tokens #5140 #5140 (1.0):
- "PAT CLI commands `create-token`, `revoke-token`, `list-tokens` have been removed; use API keys instead. - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)"
- "Authentication with tokens has been removed; use API keys instead. - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)"

## Remove support for Environments #5072 #5072 (1.0):
- "Flow 'environments' have been removed; use `RunConfig`s instead. - [#5072](https://github.com/PrefectHQ/prefect/pull/5072), [docs](https://docs.prefect.io/orchestration/flow_config/upgrade.html)"

## Flow registration:
- New flow registration CLI #4256 #4256 (1.0)
- "The `prefect register flow` command has been removed; use `prefect register` instead. - [#4256](https://github.com/PrefectHQ/prefect/pull/4256)"
- "The `prefect run flow` command has been removed; use `prefect run` instead. - [#4463](https://github.com/PrefectHQ/prefect/pull/4463)"
- The changes in flow registration require Prefect Server 2021.09.02. Prefect Server will need to be upgraded before flows can be registered from this version - #4930 (0.15.5)

## Imports have moved:
- Move artifacts functions to prefect.backend.artifacts - #5117 (0.15.8)
- "`Parameter` is not importable from `prefect.core.tasks` anymore; use `prefect.Parameter` instead."
- "Exceptions are no longer importable from `prefect.utilities.exceptions`; use `prefect.exceptions` instead. - [#4664](https://github.com/PrefectHQ/prefect/pull/4664)"
- "Executors can no longer be imported from `prefect.engine.executors`; use `prefect.executors` instead. - [#3798](https://github.com/PrefectHQ/prefect/pull/3798)"

## Schedules
- Add support for rich iCal style scheduling via RRules - #4901 (0.15.8)

## Drop support for Python 3.6 (#5136) (1.0)

## Additional changes

- Services run by prefect server cli are now local by default (listen to localhost instead of 0.0.0.0); use --expose if you want to connect from a remote location - #4821 (0.15.5)
- "The AWS Fargate agent has been removed; use the ECS agent instead. - [#3812](https://github.com/PrefectHQ/prefect/pull/3812)"
- "`DockerAgent(docker_interface=...)` will now raise an exception if passed. - [#4446](https://github.com/PrefectHQ/prefect/pull/4446)"
- "The `log_to_cloud` setting is now ignored; use `send_flow_run_logs` instead. - [#4487](https://github.com/PrefectHQ/prefect/pull/4487)"