# Changelog

## Development <Badge text="beta" type="success"/>

### Major Features

- None

### Minor Features

- None

### Fixes

- Fixed `flow.deploy()` attempting to access a nonexistant string attribute - [#503](https://github.com/PrefectHQ/prefect/pull/503)
- Ensure all logs make it to the logger service in deployment - [#508](https://github.com/PrefectHQ/prefect/issues/508)

### Breaking Changes

- Move `prefect.client.result_handlers` to `prefect.engine.result_handlers` - [#512](https://github.com/PrefectHQ/prefect/pull/512)

## 0.4.0 <Badge text="beta" type="success"/>

Released January 8, 2019

### Major Features

- Add support for Prefect Cloud - [#374](https://github.com/PrefectHQ/prefect/pull/374), [#406](https://github.com/PrefectHQ/prefect/pull/406), [#473](https://github.com/PrefectHQ/prefect/pull/473), [#491](https://github.com/PrefectHQ/prefect/pull/491)
- Add versioned serialization schemas for `Flow`, `Task`, `Parameter`, `Edge`, `State`, `Schedule`, and `Environment` objects - [#310](https://github.com/PrefectHQ/prefect/pull/310), [#318](https://github.com/PrefectHQ/prefect/pull/318), [#319](https://github.com/PrefectHQ/prefect/pull/319), [#340](https://github.com/PrefectHQ/prefect/pull/340)
- Add ability to provide `ResultHandler`s for storing private result data - [#391](https://github.com/PrefectHQ/prefect/pull/391), [#394](https://github.com/PrefectHQ/prefect/pull/394), [#430](https://github.com/PrefectHQ/prefect/pull/430/)
- Support depth-first execution of mapped tasks and tracking of both the static "parent" and dynamic "children" via `Mapped` states - [#485](https://github.com/PrefectHQ/prefect/pull/485)

### Minor Features

- Add new `TimedOut` state for task execution timeouts - [#255](https://github.com/PrefectHQ/prefect/issues/255)
- Use timezone-aware dates throughout Prefect - [#325](https://github.com/PrefectHQ/prefect/pull/325)
- Add `description` and `tags` arguments to `Parameters` - [#318](https://github.com/PrefectHQ/prefect/pull/318)
- Allow edge `key` checks to be skipped in order to create "dummy" flows from metadata - [#319](https://github.com/PrefectHQ/prefect/pull/319)
- Add new `names_only` keyword to `flow.parameters` - [#337](https://github.com/PrefectHQ/prefect/pull/337)
- Add utility for building GraphQL queries and simple schemas from Python objects - [#342](https://github.com/PrefectHQ/prefect/pull/342)
- Add links to downloadable Jupyter notebooks for all tutorials - [#212](https://github.com/PrefectHQ/prefect/issues/212)
- Add `to_dict` convenience method for `DotDict` class - [#341](https://github.com/PrefectHQ/prefect/issues/341)
- Refactor requirements to a custom `ini` file specification - [#347](https://github.com/PrefectHQ/prefect/pull/347)
- Refactor API documentation specification to `toml` file - [#361](https://github.com/PrefectHQ/prefect/pull/361)
- Add new SQLite tasks for basic SQL scripting and querying - [#291](https://github.com/PrefectHQ/prefect/issues/291)
- Executors now pass `map_index` into the `TaskRunner`s - [#373](https://github.com/PrefectHQ/prefect/pull/373)
- All schedules support `start_date` and `end_date` parameters - [#375](https://github.com/PrefectHQ/prefect/pull/375)
- Add `DateTime` marshmallow field for timezone-aware serialization - [#378](https://github.com/PrefectHQ/prefect/pull/378)
- Adds ability to put variables into context via the config - [#381](https://github.com/PrefectHQ/prefect/issues/381)
- Adds new `client.deploy` method for adding new flows to the Prefect Cloud - [#388](https://github.com/PrefectHQ/prefect/issues/388)
- Add `id` attribute to `Task` class - [#416](https://github.com/PrefectHQ/prefect/issues/416)
- Add new `Resume` state for resuming from `Paused` tasks - [#435](https://github.com/PrefectHQ/prefect/issues/435)
- Add support for heartbeats - [#436](https://github.com/PrefectHQ/prefect/issues/436)
- Add new `Submitted` state for signaling that `Scheduled` tasks have been handled - [#445](https://github.com/PrefectHQ/prefect/issues/445)
- Add ability to add custom environment variables and copy local files into `ContainerEnvironment`s - [#453](https://github.com/PrefectHQ/prefect/issues/453)
- Add `set_secret` method to Client for creating and setting the values of user secrets - [#452](https://github.com/PrefectHQ/prefect/issues/452)
- Refactor runners into `CloudTaskRunner` and `CloudFlowRunner` classes - [#431](https://github.com/PrefectHQ/prefect/issues/431)
- Added functions for loading default `engine` classes from config - [#477](https://github.com/PrefectHQ/prefect/pull/477)

### Fixes

- Fixed issue with `GraphQLResult` reprs - [#374](https://github.com/PrefectHQ/prefect/pull/374)
- `CronSchedule` produces expected results across daylight savings time transitions - [#375](https://github.com/PrefectHQ/prefect/pull/375)
- `utilities.serialization.Nested` properly respects `marshmallow.missing` values - [#398](https://github.com/PrefectHQ/prefect/pull/398)
- Fixed issue in capturing unexpected mapping errors during task runs - [#409](https://github.com/PrefectHQ/prefect/pull/409)
- Fixed issue in `flow.visualize()` so that mapped flow states can be passed and colored - [#387](https://github.com/PrefectHQ/prefect/issues/387)
- Fixed issue where `IntervalSchedule` was serialized at "second" resolution, not lower - [#427](https://github.com/PrefectHQ/prefect/pull/427)
- Fixed issue where `SKIP` signals were preventing multiple layers of mapping - [#455](https://github.com/PrefectHQ/prefect/issues/455)
- Fixed issue with multi-layer mapping in `flow.visualize()` - [#454](https://github.com/PrefectHQ/prefect/issues/454)
- Fixed issue where Prefect Cloud `cached_inputs` weren't being used locally - [#434](https://github.com/PrefectHQ/prefect/issues/434)
- Fixed issue where `Config.set_nested` would have an error if the provided key was nested deeper than an existing terminal key - [#479](https://github.com/PrefectHQ/prefect/pull/479)
- Fixed issue where `state_handlers` were not called for certain signals - [#494](https://github.com/PrefectHQ/prefect/pull/494)

### Breaking Changes

- Remove `NoSchedule` and `DateSchedule` schedule classes - [#324](https://github.com/PrefectHQ/prefect/pull/324)
- Change `serialize()` method to use schemas rather than custom dict - [#318](https://github.com/PrefectHQ/prefect/pull/318)
- Remove `timestamp` property from `State` classes - [#305](https://github.com/PrefectHQ/prefect/pull/305)
- Remove the custom JSON encoder library at `prefect.utilities.json` - [#336](https://github.com/PrefectHQ/prefect/pull/336)
- `flow.parameters` now returns a set of parameters instead of a dictionary - [#337](https://github.com/PrefectHQ/prefect/pull/337)
- Renamed `to_dotdict` -> `as_nested_dict` - [#339](https://github.com/PrefectHQ/prefect/pull/339)
- Moved `prefect.utilities.collections.GraphQLResult` to `prefect.utilities.graphql.GraphQLResult` - [#371](https://github.com/PrefectHQ/prefect/pull/371)
- `SynchronousExecutor` now does _not_ do depth first execution for mapped tasks - [#373](https://github.com/PrefectHQ/prefect/pull/373)
- Renamed `prefect.utilities.serialization.JSONField` -> `JSONCompatible`, removed its `max_size` feature, and no longer automatically serialize payloads as strings - [#376](https://github.com/PrefectHQ/prefect/pull/376)
- Renamed `prefect.utilities.serialization.NestedField` -> `Nested` - [#376](https://github.com/PrefectHQ/prefect/pull/376)
- Renamed `prefect.utilities.serialization.NestedField.dump_fn` -> `NestedField.value_selection_fn` for clarity - [#377](https://github.com/PrefectHQ/prefect/pull/377)
- Local secrets are now pulled from `secrets` in context instead of `_secrets` - [#382](https://github.com/PrefectHQ/prefect/pull/382)
- Remove Task and Flow descriptions, Flow project & version attributes - [#383](https://github.com/PrefectHQ/prefect/issues/383)
- Changed `Schedule` parameter from `on_or_after` to `after` - [#396](https://github.com/PrefectHQ/prefect/issues/396)
- Environments are immutable and return `dict` keys instead of `str`; some arguments for `ContainerEnvironment` are removed - [#398](https://github.com/PrefectHQ/prefect/pull/398)
- `environment.run()` and `environment.build()`; removed the `flows` CLI and replaced it with a top-level CLI command, `prefect run` - [#400](https://github.com/PrefectHQ/prefect/pull/400)
- The `set_temporary_config` utility now accepts a single dict of multiple config values, instead of just a key/value pair, and is located in `utilities.configuration` - [#401](https://github.com/PrefectHQ/prefect/pull/401)
- Bump `click` requirement to 7.0, which changes underscores to hyphens at CLI - [#409](https://github.com/PrefectHQ/prefect/pull/409)
- `IntervalSchedule` rejects intervals of less than one minute - [#427](https://github.com/PrefectHQ/prefect/pull/427)
- `FlowRunner` returns a `Running` state, not a `Pending` state, when flows do not finish - [#433](https://github.com/PrefectHQ/prefect/pull/433)
- Remove the `task_contexts` argument from `FlowRunner.run()` - [#440](https://github.com/PrefectHQ/prefect/pull/440)
- Remove the leading underscore from Prefect-set context keys - [#446](https://github.com/PrefectHQ/prefect/pull/446)
- Removed throttling tasks within the local cluster - [#470](https://github.com/PrefectHQ/prefect/pull/470)
- Even `start_tasks` will not run before their state's `start_time` (if the state is `Scheduled`) - [#474](https://github.com/PrefectHQ/prefect/pull/474)
- `DaskExecutor`'s "processes" keyword argument was renamed "local_processes" - [#477](https://github.com/PrefectHQ/prefect/pull/477)
- Removed the `mapped` and `map_index` kwargs from `TaskRunner.run()`. These values are now inferred automatically - [#485](https://github.com/PrefectHQ/prefect/pull/485)
- The `upstream_states` dictionary used by the Runners only includes `State` values, not lists of `States`. The use case that required lists of `States` is now covered by the `Mapped` state. - [#485](https://github.com/PrefectHQ/prefect/pull/485)

## 0.3.3 <Badge text="alpha" type="warn"/>

Released October 30, 2018

### Major Features

- Refactor `FlowRunner` and `TaskRunner` into a modular `Runner` pipelines - [#260](https://github.com/PrefectHQ/prefect/pull/260), [#267](https://github.com/PrefectHQ/prefect/pull/267)
- Add configurable `state_handlers` for `FlowRunners`, `Flows`, `TaskRunners`, and `Tasks` - [#264](https://github.com/PrefectHQ/prefect/pull/264), [#267](https://github.com/PrefectHQ/prefect/pull/267)
- Add gmail and slack notification state handlers w/ tutorial - [#274](https://github.com/PrefectHQ/prefect/pull/274), [#294](https://github.com/PrefectHQ/prefect/pull/294)

### Minor Features

- Add a new method `flow.get_tasks()` for easily filtering flow tasks by attribute - [#242](https://github.com/PrefectHQ/prefect/pull/242)
- Add new `JinjaTemplateTask` for easily rendering jinja templates - [#200](https://github.com/PrefectHQ/prefect/issues/200)
- Add new `PAUSE` signal for halting task execution - [#246](https://github.com/PrefectHQ/prefect/pull/246)
- Add new `Paused` state corresponding to `PAUSE` signal, and new `pause_task` utility - [#251](https://github.com/PrefectHQ/prefect/issues/251)
- Add ability to timeout task execution for all executors except `DaskExecutor(processes=True)` - [#240](https://github.com/PrefectHQ/prefect/issues/240)
- Add explicit unit test to check Black formatting (Python 3.6+) - [#261](https://github.com/PrefectHQ/prefect/pull/261)
- Add ability to set local secrets in user config file - [#231](https://github.com/PrefectHQ/prefect/issues/231), [#274](https://github.com/PrefectHQ/prefect/pull/274)
- Add `is_skipped()` and `is_scheduled()` methods for `State` objects - [#266](https://github.com/PrefectHQ/prefect/pull/266), [#278](https://github.com/PrefectHQ/prefect/pull/278)
- Adds `now()` as a default `start_time` for `Scheduled` states - [#278](https://github.com/PrefectHQ/prefect/pull/278)
- `Signal` classes now pass arguments to underlying `State` objects - [#279](https://github.com/PrefectHQ/prefect/pull/279)
- Run counts are tracked via `Retrying` states - [#281](https://github.com/PrefectHQ/prefect/pull/281)

### Fixes

- Flow consistently raises if passed a parameter that doesn't exist - [#149](https://github.com/PrefectHQ/prefect/issues/149)

### Breaking Changes

- Renamed `scheduled_time` -> `start_time` in `Scheduled` state objects - [#278](https://github.com/PrefectHQ/prefect/pull/278)
- `TaskRunner.check_for_retry` no longer checks for `Retry` states without `start_time` set - [#278](https://github.com/PrefectHQ/prefect/pull/278)
- Swapped the position of `result` and `message` attributes in State initializations, and started storing caught exceptions as results - [#283](https://github.com/PrefectHQ/prefect/issues/283)

## 0.3.2 <Badge text="alpha" type="warn"/>

Released October 2, 2018

### Major Features

- Local parallelism with `DaskExecutor` - [#151](https://github.com/PrefectHQ/prefect/issues/151), [#186](https://github.com/PrefectHQ/prefect/issues/186)
- Resource throttling based on `tags` - [#158](https://github.com/PrefectHQ/prefect/issues/158), [#186](https://github.com/PrefectHQ/prefect/issues/186)
- `Task.map` for mapping tasks - [#186](https://github.com/PrefectHQ/prefect/issues/186)
- Added `AirFlow` utility for importing Airflow DAGs as Prefect Flows - [#232](https://github.com/PrefectHQ/prefect/pull/232)

### Minor Features

- Use Netlify to deploy docs - [#156](https://github.com/prefecthq/prefect/issues/156)
- Add changelog - [#153](https://github.com/prefecthq/prefect/issues/153)
- Add `ShellTask` - [#150](https://github.com/prefecthq/prefect/issues/150)
- Base `Task` class can now be run as a dummy task - [#191](https://github.com/PrefectHQ/prefect/pull/191)
- New `return_failed` keyword to `flow.run()` for returning failed tasks - [#205](https://github.com/PrefectHQ/prefect/pull/205)
- some minor changes to `flow.visualize()` for visualizing mapped tasks and coloring nodes by state - [#202](https://github.com/PrefectHQ/prefect/issues/202)
- Added new `flow.replace()` method for swapping out tasks within flows - [#230](https://github.com/PrefectHQ/prefect/pull/230)
- Add `debug` kwarg to `DaskExecutor` for optionally silencing dask logs - [#209](https://github.com/PrefectHQ/prefect/issues/209)
- Update `BokehRunner` for visualizing mapped tasks - [#220](https://github.com/PrefectHQ/prefect/issues/220)
- Env var configuration settings are typed - [#204](https://github.com/PrefectHQ/prefect/pull/204)
- Implement `map` functionality for the `LocalExecutor` - [#233](https://github.com/PrefectHQ/prefect/issues/233)

### Fixes

- Fix issue with Versioneer not picking up git tags - [#146](https://github.com/prefecthq/prefect/issues/146)
- `DotDicts` can have non-string keys - [#193](https://github.com/prefecthq/prefect/issues/193)
- Fix unexpected behavior in assigning tags using contextmanagers - [#190](https://github.com/PrefectHQ/prefect/issues/190)
- Fix bug in initialization of Flows with only `edges` - [#225](https://github.com/PrefectHQ/prefect/pull/225)
- Remove "bottleneck" when creating pipelines of mapped tasks - [#224](https://github.com/PrefectHQ/prefect/pull/224)

### Breaking Changes

- Runner refactor - [#221](https://github.com/PrefectHQ/prefect/pull/221)
- Cleaned up signatures of `TaskRunner` methods - [#171](https://github.com/prefecthq/prefect/issues/171)
- Locally, Python 3.4 users can not run the more advanced parallel executors (`DaskExecutor`) [#186](https://github.com/PrefectHQ/prefect/issues/186)

## 0.3.1 <Badge text="alpha" type="warn"/>

Released September 6, 2018

### Major Features

- Support for user configuration files - [#195](https://github.com/PrefectHQ/prefect/pull/195)

### Minor Features

- None

### Fixes

- Let DotDicts accept non-string keys - [#193](https://github.com/PrefectHQ/prefect/pull/193), [#194](https://github.com/PrefectHQ/prefect/pull/194)

### Breaking Changes

- None

## 0.3.0 <Badge text="alpha" type="warn"/>

Released August 20, 2018

### Major Features

- BokehRunner - [#104](https://github.com/prefecthq/prefect/issues/104), [#128](https://github.com/prefecthq/prefect/issues/128)
- Control flow: `ifelse`, `switch`, and `merge` - [#92](https://github.com/prefecthq/prefect/issues/92)
- Set state from `reference_tasks` - [#95](https://github.com/prefecthq/prefect/issues/95), [#137](https://github.com/prefecthq/prefect/issues/137)
- Add flow `Registry` - [#90](https://github.com/prefecthq/prefect/issues/90)
- Output caching with various `cache_validators` - [#84](https://github.com/prefecthq/prefect/issues/84), [#107](https://github.com/prefecthq/prefect/issues/107)
- Dask executor - [#82](https://github.com/prefecthq/prefect/issues/82), [#86](https://github.com/prefecthq/prefect/issues/86)
- Automatic input caching for retries, manual-only triggers - [#78](https://github.com/prefecthq/prefect/issues/78)
- Functional API for `Flow` definition
- `State` classes
- `Signals` to transmit `State`

### Minor Features

- Add custom syntax highlighting to docs - [#141](https://github.com/prefecthq/prefect/issues/141)
- Add `bind()` method for tasks to call without copying - [#132](https://github.com/prefecthq/prefect/issues/132)
- Cache expensive flow graph methods - [#125](https://github.com/prefecthq/prefect/issues/125)
- Docker environments - [#71](https://github.com/prefecthq/prefect/issues/71)
- Automatic versioning via Versioneer - [#70](https://github.com/prefecthq/prefect/issues/70)
- `TriggerFail` state - [#67](https://github.com/prefecthq/prefect/issues/67)
- State classes - [#59](https://github.com/prefecthq/prefect/issues/59)

### Fixes

- None

### Breaking Changes

- None
