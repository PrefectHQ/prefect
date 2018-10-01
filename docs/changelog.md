---
sidebarDepth: 1
---

# Prefect Changelog

## 0.3.2

### Major Features

- Local parallelism with `DaskExecutor`
- Resource throttling based on `tags`
- `Task.map` for mapping tasks
- Added `AirFlow` utility for importing Airflow DAGs as Prefect Flows

### Minor Features

- Use Netlify to deploy docs
- Add changelog
- Add `ShellTask`
- Base `Task` class can now be run as a dummy task
- New `return_failed` keyword to `flow.run()` for returning failed tasks
- Some minor changes to `flow.visualize()` for visualizing mapped tasks and coloring nodes by state
- Added new `flow.replace()` method for swapping out tasks within flows
- Add `debug` kwarg to `DaskExecutor` for optionally silencing dask logs
- Update `BokehRunner` for visualizing mapped tasks
- Env var configuration settings are typed
- Support for user configuration files

### Fixes

- Fix issue with Versioneer not picking up git tags
- `DotDicts` can have non-string keys
- Fix unexpected behavior in assigning tags using contextmanagers
- Fix bug in initialization of Flows with only `edges`
- Remove "bottleneck" when creating pipelines of mapped tasks

### Breaking Changes

- Runner refactor
- Cleaned up signatures of `TaskRunner` methods
- Locally, Python 3.4 users can not run the more advanced parallel executors (`DaskExecutor`)

## 0.3.1 <Badge text="alpha" type="warn">

### Major Features

- Support for user configuration files

### Minor Features

- None

### Fixes

- Let DotDicts accept non-string keys

### Breaking Changes

- None

## 0.3.0

### Major Features

- BokehRunner
- Control flow: `ifelse`, `switch`, and `merge`
- Set state from `reference_tasks`
- Add flow `Registry`
- Output caching with various `cache_validators`
- Dask executor
- Automatic input caching for retries, manual-only triggers
- Functional API for `Flow` definition
- `State` classes
- `Signals` to transmit `State`

### Minor Features

- Add custom syntax highlighting to docs
- Add `bind()` method for tasks to call without copying
- Cache expensive flow graph methods
- Docker environments
- Automatic versioning via Versioneer
- `TriggerFail` state
- State classes

### Fixes

- None

### Breaking Changes

- None
