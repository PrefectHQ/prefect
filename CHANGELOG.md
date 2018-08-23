# Prefect Changelog

## 0.4.0 <Badge text="development" type="warn">

### Major Features
- Local parallelism with `DaskExecutor` (#151)
- Resource throttling based on `tags` (#158)

### Minor Features
- Use Netlify to deploy docs (#156)
- Add changelog (#153)
- `ShellTask` (#150)

### Fixes
- Fix issue with versioneer not picking up git tags (#146)

### Breaking Changes
- Cleaned up signatures of TaskRunner methods (#171)


## 0.3.0 <Badge text="alpha" type="warn">

0.3.0 is the preview release of Prefect.

### Major Features
- BokehRunner (#104, #128)
- Control flow: `ifelse`, `switch`, and `merge` (#92)
- Set state from `reference_tasks` (#95, #137)
- Add flow `Registry` (#90)
- Output caching with various `cache_validators` (#84, #107)
- Dask executor (#82, #86)
- Automatic input caching for retries, manual-only triggers (#78)
- Functional API for `Flow` definition
- `State` classes
- `Signals` to transmit `State`

### Minor Features
- Add custom syntax highlighting to docs (#141)
- Add `bind()` method for tasks to call without copying (#132)
- Cache expensive flow graph methods (#125)
- Docker environments (#71)
- Automatic versioning via Versioneer (#70)
- `TriggerFail` state (#67)
- State classes (#59)

### Fixes
- None

### Breaking Changes
- None
