# Prefect Changelog

## 0.4.0 <Badge text="development" type="warn">

### Major Features
- Local parallelism with `DaskExecutor` ([#151](../../issues/151))
- Resource throttling based on `tags` ([#158](../../issues/158))

### Minor Features
- Use Netlify to deploy docs ([#156](../../issues/156))
- Add changelog ([#153](../../issues/153))
- `ShellTask` ([#150](../../issues/150))

### Fixes
- Fix issue with versioneer not picking up git tags ([#146](../../issues/146))
- DotDicts can have non-string keys ([#193](../../issues/193))

### Breaking Changes
- Cleaned up signatures of TaskRunner methods ([#171](../../issues/171))


## 0.3.0 <Badge text="alpha" type="warn">

0.3.0 is the preview release of Prefect.

### Major Features
- BokehRunner ([#104](../../issues/104), [#128](../../issues/128))
- Control flow: `ifelse`, `switch`, and `merge` ([#92](../../issues/92))
- Set state from `reference_tasks` ([#95](../../issues/95), [#137](../../issues/137))
- Add flow `Registry` ([#90](../../issues/90))
- Output caching with various `cache_validators` ([#84](../../issues/84), [#107](../../issues/107))
- Dask executor ([#82](../../issues/82), [#86](../../issues/86))
- Automatic input caching for retries, manual-only triggers ([#78](../../issues/78))
- Functional API for `Flow` definition
- `State` classes
- `Signals` to transmit `State`

### Minor Features
- Add custom syntax highlighting to docs ([#141](../../issues/141))
- Add `bind()` method for tasks to call without copying ([#132](../../issues/132))
- Cache expensive flow graph methods ([#125](../../issues/125))
- Docker environments ([#71](../../issues/71))
- Automatic versioning via Versioneer ([#70](../../issues/70))
- `TriggerFail` state ([#67](../../issues/67))
- State classes ([#59](../../issues/59))

### Fixes
- None

### Breaking Changes
- None
