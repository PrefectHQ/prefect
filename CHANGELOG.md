# Prefect Changelog

## Development <Badge text="alpha" type="warn"/>

### Major Features

- Add versioned serialization schemas for `Flow`, `Task`, `Parameter`, `Edge`, `State`, `Schedule`, and `Environment` objects - [#310](https://github.com/PrefectHQ/prefect/pull/310), [#318](https://github.com/PrefectHQ/prefect/pull/318), [#319](https://github.com/PrefectHQ/prefect/pull/319), [#340](https://github.com/PrefectHQ/prefect/pull/340)

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

### Fixes

- `CronSchedule` produces expected results across daylight savings time transitions - [#375](https://github.com/PrefectHQ/prefect/pull/375)

### Breaking Changes

- Remove `NoSchedule` and `DateSchedule` schedule classes - [#324](https://github.com/PrefectHQ/prefect/pull/324)
- Change `serialize()` method to use schemas rather than custom dict - [#318](https://github.com/PrefectHQ/prefect/pull/318)
- Remove `timestamp` property from `State` classes - [#305](https://github.com/PrefectHQ/prefect/pull/305)
- Remove the custom JSON encoder library at `prefect.utilities.json` - [#336](https://github.com/PrefectHQ/prefect/pull/336)
- `flow.parameters` now returns a set of parameters instead of a dictionary - [#337](https://github.com/PrefectHQ/prefect/pull/337)
- Renamed `to_dotdict` -> `as_nested_dict` - [#339](https://github.com/PrefectHQ/prefect/pull/339)
- Moved `prefect.utilities.collections.GraphQLResult` to `prefect.utilities.graphql.GraphQLResult` - [#371](https://github.com/PrefectHQ/prefect/pull/371)
- `SynchronousExecutor` now does _not_ do depth first execution for mapped tasks - [#373](https://github.com/PrefectHQ/prefect/pull/373)

## 0.3.3 <Badge text="alpha" type="warn"/>

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

### Major Features

- Support for user configuration files - [#195](https://github.com/PrefectHQ/prefect/pull/195)

### Minor Features

- None

### Fixes

- Let DotDicts accept non-string keys - [#194](https://github.com/PrefectHQ/prefect/pull/194)

### Breaking Changes

- None

## 0.3.0 <Badge text="alpha" type="warn"/>

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
