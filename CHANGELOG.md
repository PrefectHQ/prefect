# Prefect Changelog

## 0.4.0 <Badge text="development" type="warn">

### Major Features
- Local parallelism with `DaskExecutor` [#151](https://github.com/PrefectHQ/prefect/issues/151), [#186](https://github.com/PrefectHQ/prefect/issues/186)
- Resource throttling based on `tags` [#158](https://github.com/PrefectHQ/prefect/issues/158), [#186](https://github.com/PrefectHQ/prefect/issues/186)
- `Task.map` for mapping tasks [#186](https://github.com/PrefectHQ/prefect/issues/186)

### Minor Features

- Use Netlify to deploy docs - [#156](https://github.com/prefecthq/prefect/issues/156)
- Add changelog - [#153](https://github.com/prefecthq/prefect/issues/153)
- `ShellTask` - [#150](https://github.com/prefecthq/prefect/issues/150)

### Fixes

- Fix issue with Versioneer not picking up git tags - [#146](https://github.com/prefecthq/prefect/issues/146)
- `DotDicts` can have non-string keys - [#193](https://github.com/prefecthq/prefect/issues/193)

### Breaking Changes
- Cleaned up signatures of `TaskRunner` methods - [#171](https://github.com/prefecthq/prefect/issues/171)
- Locally, Python 3.4 users can not run the more advanced parallel executors (`DaskExecutor`) [#186](https://github.com/PrefectHQ/prefect/issues/186)

## 0.3.0 <Badge text="alpha" type="warn">

0.3.0 is the preview release of Prefect.

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
