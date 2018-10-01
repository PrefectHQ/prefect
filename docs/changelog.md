---
sidebarDepth: 1
---

# Prefect Changelog

## 0.3.2

### Major Features
- Local parallelism with `DaskExecutor` 
- Resource throttling based on `tags` 
- `Task.map` for mapping tasks 
- added `AirFlow` utility for importing Airflow DAGs as Prefect Flows

### Minor Features

- Use Netlify to deploy docs
- Add changelog
- `ShellTask`
- Base `Task` class can now be run as a dummy task
- new `return_failed` keyword to `flow.run()` for returning failed tasks
- some minor changes to `flow.visualize()` for visualizing mapped tasks and coloring nodes by state
- added new `flow.replace()` method for swapping out tasks within flows
- add `debug` kwarg to `DaskExecutor` for optionally silencing dask logs 
- update `BokehRunner` for visualizing mapped tasks

### Fixes

- Fix issue with Versioneer not picking up git tags
- `DotDicts` can have non-string keys
- Fix unexpected behavior in assigning tags using contextmanagers
- Fix bug in initialization of Flows with only `edges`

### Breaking Changes
- Cleaned up signatures of `TaskRunner` methods
- Locally, Python 3.4 users can not run the more advanced parallel executors (`DaskExecutor`)

## 0.3.0

0.3.0 is the initial preview release of Prefect.

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
