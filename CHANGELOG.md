# Changelog

## 1.2.2 <Badge text="beta" type="success" />

Released on May 24, 2022.

### Enhancements

- Add inference of Docker network mode for "host" and "none" networks - [#5748](https://github.com/PrefectHQ/prefect/pull/5748)
- Add Python 3.10 support - [#5770](https://github.com/PrefectHQ/prefect/pull/5770)
- Raise error on task initialiation when positional-only parameters are present in function signature - [#5789](https://github.com/PrefectHQ/prefect/pull/5789)
- Add flag to prevent printing ASCII welcome message [5619](https://github.com/PrefectHQ/prefect/issues/5619)
- Allow the Prefect client to retry connections for HTTP targets - [#5825](https://github.com/PrefectHQ/prefect/pull/5825)
### Task Library

- Adds SFTP server tasks `SftpUpload` and `SftpDownload` [#1234](https://github.com/PrefectHQ/prefect/pull/5740)
- Configure logging output for `AirbyteConnectionTask` - [#5794](https://github.com/PrefectHQ/prefect/pull/5794)
- Make artifacts optional in `StartFlowRun` - [#5795](https://github.com/PrefectHQ/prefect/pull/5795)
- Use `json` instead of `dict` for `DatabricksSubmitMultitaskRun` - [#5728](https://github.com/PrefectHQ/prefect/pull/5728)
- Fix defect in serialization of Great Expectation's results in `LocalResult` - [#5724](https://github.com/PrefectHQ/prefect/pull/5724)
- Add an optional `data_security_mode` to Databricks cluster configuration. - [#5778](https://github.com/PrefectHQ/prefect/pull/5778)

### Fixes

- Fix bug where Prefect signals in tasks were not re-raised by the process-based timeout handler - [#5804](https://github.com/PrefectHQ/prefect/pull/5804)
- Update flow builds to be deterministic when upstream and downstream slug are same - [#5785](https://github.com/PrefectHQ/prefect/pull/5785)

### Contributors

- [David McGuire](https://github.com/dmcguire81)
- [Jaakko Lappalainen](https://github.com/jkklapp)
- [Jason Bertman](https://github.com/jbertman)
- [Joël Luijmes](https://github.com/joelluijmes)
- [Karthikeyan Singaravelan](https://github.com/tirkarthi)
- [Mate Hricz](https://github.com/Matt9993)
- [Nico Neumann](https://github.com/neumann-nico)
- [Robert Phamle](https://github.com/rphamle)

## 1.2.1 <Badge text="beta" type="success" />

Released on April 27, 2022.

### Enhancements

- Add ability to set a `max_duration` timeout in `wait_for_flow_run` task - [#5669](https://github.com/PrefectHQ/prefect/issues/5669)
- Add pipe support for `EdgeAnnotation` types, e.g. `map` - [#5674](https://github.com/PrefectHQ/prefect/pull/5674)
- Add 'gs' as a valid filesystem schema for reading specifications - [#5705](https://github.com/PrefectHQ/prefect/pull/5705)
- Add REPL mode for CLI - [#5615](https://github.com/PrefectHQ/prefect/pull/5615)

### Fixes

- Fix bug where settings the backend to "server" would not prevent client from requesting secrets from the API - [#5637](https://github.com/PrefectHQ/prefect/pull/5637)
- Fix docker-in-docker issue in `DockerAgent` on Windows - [#5657](https://github.com/PrefectHQ/prefect/pull/5657)
- Fix graphviz syntax error when visualizing a flow with a task which is a mapped lambda - [#5662](https://github.com/PrefectHQ/prefect/pull/5662)
- Allow `prefect run` parameters to include equals ("=") signs - [#5716](https://github.com/PrefectHQ/prefect/pull/5716)
### Task library

- Add `HightouchRunSync` task - [#5672](https://github.com/PrefectHQ/prefect/pull/5672)
- Fix `DbtCloudRunJob` task failing with nested input for additional_args - [#5706](https://github.com/PrefectHQ/prefect/issues/5706)"
- Fix Databricks new cluster API params: autoscale and policy_id - [#5681](https://github.com/PrefectHQ/prefect/pull/5681)
### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Anders Segerberg](https://github.com/gtasegerberg)
- [Ben Ayers-Glassey](https://github.com/bayersglassey-zesty/)
- [Dominick Olivito](https://github.com/olivito)
- [Karthikeyan Singaravelan](https://github.com/tirkarthi)
- [Mahmoud Lababidi](https://github.com/lababidi)
- [limx0](https://github.com/limx0)
- [oscarwyatt](https://github.com/oscarwyatt)
- [satoshiking](https://github.com/satoshiking)

## 1.2.0 <Badge text="beta" type="success" />

Released on April 5, 2022.

### Features

- Add `retry_on` to allow tasks to retry on a subset of exception types - [#5634](https://github.com/PrefectHQ/prefect/pull/5634)

### Enhancements

- Add ability to add capacity provider for ECS flow runs - [#4356](https://github.com/PrefectHQ/prefect/issues/4356)
- Add support for default values to `DateTimeParameter` - [#5519](https://github.com/PrefectHQ/prefect/pull/5519)
- Calling `flow.run` within a flow definition context will raise a `RuntimeError` - [#5588](https://github.com/PrefectHQ/prefect/pull/5588)
- Add support for service principal and managed identities for storage on Azure - [#5612](https://github.com/PrefectHQ/prefect/pull/5612)

### Task Library

- The `azureml-sdk` dependency has been moved from the `azure` extra into `azureml` - [#5632](https://github.com/PrefectHQ/prefect/pull/5632)
- Add task to create materializations with [Transform](https://transform.co/) - [#5518](https://github.com/PrefectHQ/prefect/pull/5518)
- Add `create_bucket` to `GCSCopy` - [#5618](https://github.com/PrefectHQ/prefect/issues/5618)

### Fixes

- Fix issue where the `FlowRunView` could fail to initialize when the backend has no state data - [#5554](https://github.com/PrefectHQ/prefect/pull/5554)
- Fix issue where adaptive Dask clusters failed to replace workers - [#5549](https://github.com/PrefectHQ/prefect/issues/5549)
- Fix issue where logging in to Cloud via the CLI could fail - [#5643](https://github.com/PrefectHQ/prefect/pull/5643)

### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Emre Akgün](https://github.com/Fraznist)
- [Josh Wang](https://github.com/wangjoshuah)
- [Panagiotis Simakis](https://github.com/sp1thas)
- [eedokl](https://github.com/eedokl)

## 1.1.0 <Badge text="beta" type="success" />

Released on March 10, 2022.

### Features

- Add `.pipe` operator to `prefect.Task` for functional chaining - [#5507](https://github.com/PrefectHQ/prefect/pull/5507)
- Add Kubernetes authentication support to `VaultSecret` - [#5412](https://github.com/PrefectHQ/prefect/pull/5412)

### Enhancement

- Allow tasks to consume `self` as an argument - [#5508](https://github.com/PrefectHQ/prefect/pull/5508)
- Improve the default idempotency key for `create_flow_run` task when mapping during a local flow run - [#5443](https://github.com/PrefectHQ/prefect/pulls/5443)

### Fixes

- Fix the broken URL displayed in `entrypoint.sh` - [#5490](https://github.com/PrefectHQ/prefect/pull/5490)
- Fix zombie processes created by Hasura container during `prefect server start` - [#5476](https://github.com/PrefectHQ/prefect/pull/5479)

### Task Library

- Add Airbyte configuration export task - [#5410](https://github.com/PrefectHQ/prefect/pull/5410)
- Update `Glob` task to accept a string path - [#5499](https://github.com/PrefectHQ/prefect/pull/54990)
- Fix pod logging while using `RunNamespacedJob` - [#5514](https://github.com/PrefectHQ/prefect/pull/5514)
- Add `include_generated_sql` option to `CubeJSQueryTask` - [#5471](https://github.com/PrefectHQ/prefect/pull/5471)

### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Andrew Klimovski](https://github.com/klimbot)
- [Brett Polivka](https://github.com/polivbr)
- [Jamie Dick](https://github.com/jamiedick)
- [Michael Milton](https://github.com/multimeric)
- [Paul Gierz](https://github.com/pgierz)
- [VincentAntoine](https://github.com/VincentAntoine)
- [pseudoyim](https://github.com/pseudoyim)

## 1.0.0 <Badge text="beta" type="success" />

Released on February 23, 2022.

### Highlights

- Authentication with tokens has been removed; use API keys instead. - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Python 3.6 is no longer supported; use Python 3.7+ instead. - [#5136](https://github.com/PrefectHQ/prefect/pull/5136)
- Flow `Environment`s have been removed; use `RunConfig`s instead. - [#5072](https://github.com/PrefectHQ/prefect/pull/5072), [docs](https://docs.prefect.io/orchestration/flow_config/upgrade.html)
- We have a new [Discourse community](https://discourse.prefect.io/) to encourage lasting discussions.

### Breaking Changes

<!-- agent changes -->
- The AWS Fargate agent has been removed; use the ECS agent instead. - [#3812](https://github.com/PrefectHQ/prefect/pull/3812)
- `DockerAgent(docker_interface=...)` will now raise an exception if passed. - [#4446](https://github.com/PrefectHQ/prefect/pull/4446)
- Agents will no longer check for authentication at the `prefect.cloud.agent.auth_token` config key. - [#5140](https://github.com/PrefectHQ/prefect/pull/5140)
<!-- name/import changes -->
- Executors can no longer be imported from `prefect.engine.executors`; use `prefect.executors` instead. - [#3798](https://github.com/PrefectHQ/prefect/pull/3798)
- `Parameter` is not importable from `prefect.core.tasks` anymore; use `prefect.Parameter` instead.
- Exceptions are no longer importable from `prefect.utilities.exceptions`; use `prefect.exceptions` instead. - [#4664](https://github.com/PrefectHQ/prefect/pull/4664)
- `Client.login_to_tenant` has been renamed to `Client.switch_tenant`.
<!-- cli changes -->
- The `prefect register flow` command has been removed; use `prefect register` instead. - [#4256](https://github.com/PrefectHQ/prefect/pull/4256)
- The `prefect run flow` command has been removed; use `prefect run` instead. - [#4463](https://github.com/PrefectHQ/prefect/pull/4463)
- Authentication token CLI commands `create-token`, `revoke-token`, `list-tokens` have been removed; use API keys instead. - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- `prefect auth login` no longer accepts authentication tokens. - [#5140](https://github.com/PrefectHQ/prefect/pull/5140)
- `prefect auth purge-tokens` has been added to delete the Prefect-managed tokens directory. - [#5140](https://github.com/PrefectHQ/prefect/pull/5140)
<!-- config changes -->
- The `log_to_cloud` setting is now ignored; use `send_flow_run_logs` instead. - [#4487](https://github.com/PrefectHQ/prefect/pull/4487)

### Enhancements

- Update `LocalDaskExecutor` to use new Python futures feature. - [#5046](https://github.com/PrefectHQ/prefect/issues/5046)
- Add a `State.__sizeof__` implementation to include the size of its result for better scheduling. - [#5304](https://github.com/PrefectHQ/prefect/pull/5304)
- Allow the cancellation event check to be disabled in the `DaskExecutor`. - [#5443](https://github.com/PrefectHQ/prefect/issues/5443)
- Update `Flow.visualize()` to allow change in orientation. - [#5472](https://github.com/PrefectHQ/prefect/pull/5472)
- Allow ECS task definition role ARNs to override ECS agent defaults. - [#5366](https://github.com/PrefectHQ/prefect/pull/5366)

### Task Library

- Add `DatabricksGetJobID` to retreive Databricks job IDs with a given name. - [#5438](https://github.com/PrefectHQ/prefect/issues/5438)
- Add `AWSParametersManager` task to retrieve value from AWS Systems Manager Parameter Store. - [#5439](https://github.com/PrefectHQ/prefect/issues/5439)
- Update `SpacyNLP` task to support `spacy` version >= 3.0. - [#5358](https://github.com/PrefectHQ/prefect/issues/5358)
- Add `exclude` parameter to `SpacyNLP` task. - [#5402](https://github.com/PrefectHQ/prefect/pull/5402)
- Update the `AWSSecretsManager` task to parse non key-value type secrets. - [#5451](https://github.com/PrefectHQ/prefect/issues/5451)
- Update the `DatabricksRunNow` task to use the Databricks 2.1 jobs API. - [#5395](https://github.com/PrefectHQ/prefect/pull/5395/)
- Add `ge_checkpoint` and `checkpoint_kwargs` parameters to `RunGreatExpectationsValidation` to allow runtime configuration of checkpoint runs. - [#5404](https://github.com/PrefectHQ/prefect/pull/5404)
- Add support for overwriting existing blobs when using Azure `BlobStorageUpload` task. - [#5437](https://github.com/PrefectHQ/prefect/pull/5437)
- Add `Neo4jRunCypherQueryTask` task for running Cypher queries against Neo4j databases. - [#5418](https://github.com/PrefectHQ/prefect/pull/5418)
- Add `DatabricksSubmitMultitaskRun` task to run Databricks jobs with multiple Databricks tasks.  - [#5395](https://github.com/PrefectHQ/prefect/pull/5395/)

### Fixes

- Add support to `prefect.flatten` for non-iterable upstreams, including exceptions and signals. - [#4084](https://github.com/PrefectHQ/prefect/issues/4084)
- While building Docker images for storage, `rm=True` is used as default, which deletes intermediate containers. - [#5384](https://github.com/PrefectHQ/prefect/issues/5384)
- Use `__all__` to declare Prefect's public API for Pyright. - [#5293](https://github.com/PrefectHQ/prefect/pull/5293)
- Fix usage of `sys.getsizeof` to restore support for PyPy. - [#5390](https://github.com/PrefectHQ/prefect/issues/5390)
- Fix issues with log size estimates from [#5316](https://github.com/PrefectHQ/prefect/pull/5316). - [#5390](https://github.com/PrefectHQ/prefect/issues/5390)


### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Aneesh Makala](https://github.com/makalaaneesh)
- [Connor Martin](https://github.com/cjmartian)
- [Gebing](https://github.com/gebing)
- [Julio Faracco](https://github.com/jcfaracco)
- [Kevin Mullins](https://github.com/zyzil)
- [Mathijs Miermans](https://github.com/mmiermans)
- [Oliver Mannion](https://github.com/tekumara)
- [Raymond Yu](https://github.com/raymonds-backyard)


## 0.15.13 <Badge text="beta" type="success" />

Released on January 25, 2022.

### Enhancements

- Ensure that maximum log payload sizes are not exceeded - [#5316](https://github.com/PrefectHQ/prefect/pull/5316)

### Fixes

- Fix bug where logout was required before logging in with a new key if the new key does not have access to the old tenant - [#5355](https://github.com/PrefectHQ/prefect/pull/5355)

### Server

- Upgrade Hasura to v2.1.1 which includes support for Apple M1 - [#5335](https://github.com/PrefectHQ/prefect/pull/5335)

### Task Library

- Fix bug where the Airbyte sync job failure would not be reflected in the task state - [#5362](https://github.com/PrefectHQ/prefect/pull/5362)

## 0.15.12 <Badge text="beta" type="success" />

Released on January 12, 2022.

### Enhancements

- Allow passing timedeltas to `create_flow_run` to schedule subflows at runtime - [#5303](https://github.com/PrefectHQ/prefect/pull/5303)
- Upgrade Prefect Server Hasura image to 2.0.9 - [#5173](https://github.com/PrefectHQ/prefect/pull/5313)
- Allow client retries on failed requests to Prefect Server - [#5292](https://github.com/PrefectHQ/prefect/pull/5292)

### Task Library


- Add authentication parameter for Snowflake query tasks - [#5173](https://github.com/PrefectHQ/prefect/pull/5173)
- Add Mixpanel tasks - [#5276](https://github.com/PrefectHQ/prefect/pull/5276)
- Add Zendesk Tickets Incremental Export task - [#5278](https://github.com/PrefectHQ/prefect/pull/5278)
- Add Cube.js Query task - [#5280](https://github.com/PrefectHQ/prefect/pull/5280)
- Add Monte Carlo lineage tasks - [#5256](https://github.com/PrefectHQ/prefect/pull/5256)
- Add Firebolt task - [#5265](https://github.com/PrefectHQ/prefect/pull/5265)
- Add custom domain support to dbt Cloud tasks for enterprise customers - [#5273](https://github.com/PrefectHQ/prefect/pull/5273)
- Fix response key in Airbyte task health check - [#5314](https://github.com/PrefectHQ/prefect/pull/5314)
- Allow all Postgres task parameters to be configured at runtime - [#4377](https://github.com/PrefectHQ/prefect/pull/5016)
- Fix `AirbyteConnectionTask` requiring optional parameters - [#5260](https://github.com/PrefectHQ/prefect/pull/5260)
- Allow `StepActivate` task to receive runtime parameters - [#5231](https://github.com/PrefectHQ/prefect/pull/5231)

### Fixes

- Fix bug where null `run_config` field caused deserialization errors in backend views  - [#1234](https://github.com/PrefectHQ/prefect/pull/1234)

### Contributors

- [Adam Brusselback](https://github.com/Tostino)
- [Ahmed Ezzat](https://github.com/bitthebyte)
- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Connor Martin](https://github.com/cjmartian)
- [Dennis Hinnenkamp](https://github.com/sikwel)
- [Gaylord Cherencey](https://github.com/gcherencey)
- [Henning Holgersen](https://github.com/radbrt)
- [Mathijs Miermans](https://github.com/mmiermans)
- [Michał Zawadzki](https://github.com/Trymzet)
- [Raghav Sharma](https://github.com/raghavSharmaSigmoid)

## 0.15.11 <Badge text="beta" type="success" />

Released on December 22, 2021.

### Enhancements

- Allow passing kwargs to `Merge` task constructor via `merge()` function - [#5233](https://github.com/PrefectHQ/prefect/pull/5233)
- Allow passing proxies to `slack_notifier` - [#5237](https://github.com/PrefectHQ/prefect/pull/5237)

### Fixes

- Update `RunGreatExpectationsValidation` task to work with latest version of `great_expectations` - [#5172](https://github.com/PrefectHQ/prefect/issues/5172)
- Allow unsetting kubernetes `imagePullSecrets` with an empty string - [#5001](https://github.com/PrefectHQ/prefect/pull/5001)
- Improve agent handling of kubernetes jobs for flow runs that have been deleted - [#5190](https://github.com/PrefectHQ/prefect/pull/5190)
- Remove `beta1` from kubernetes agent template - [#5194](https://github.com/PrefectHQ/prefect/pull/5194)
- Documentation improvements - [#5220](https://github.com/PrefectHQ/prefect/pull/5220), [#5232](https://github.com/PrefectHQ/prefect/pull/5232), [#5288](https://github.com/PrefectHQ/prefect/pull/5288)

### Contributors

- [Connor Martin](https://github.com/cjmartian)
- [Farley Farley](https://github.com/AndrewFarley)
- [Vincent Chéry](https://github.com/VincentAntoine)

## 0.15.10 <Badge text="beta" type="success" />

Released on November 30, 2021.

### Enhancements

- Add `end_time` to `FlowRunView.get_logs` - [#5138](https://github.com/PrefectHQ/prefect/pull/5138)
- Update `watch_flow_run` to stream logs immediately instead of waiting for flow run state changes - [#5138](https://github.com/PrefectHQ/prefect/pull/5138)
- Allow setting container ports for `DockerRun` - [#5130](https://github.com/PrefectHQ/prefect/issues/5130)
- Clarify `ECSRun` documentation, especially the ambiguities in setting IAM roles - [#5110](https://github.com/PrefectHQ/prefect/issues/5110)
- Fix deprecated usage of `marshmallow.fields.Dict` in RRule schedules - [#4540](https://github.com/PrefectHQ/prefect/issues/4540), [#4903](https://github.com/PrefectHQ/prefect/pull/4903)

### Fixes

- Fix connection to local server instances when using `DockerAgent` on linux - [#5182](https://github.com/PrefectHQ/prefect/pull/5182)

### Task Library

- Add support for triggering [Airbyte](https://airbyte.io/) connection sync jobs using `AirbyteConnectionTask` - [#5078](https://github.com/PrefectHQ/prefect/pull/5078)
- Add artifact publishing to `DbtCloudRunJob` task - [#5135](https://github.com/PrefectHQ/prefect/pull/5135)
- Add support for running data quality checks on Spark DataFrames using `soda-spark` - [#4901](https://github.com/PrefectHQ/prefect/pull/5144)


### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Nicholas Hemley](https://github.com/iamniche-too)
- [Shahil Mawjee](https://github.com/s-mawjee)

## 0.15.9 <Badge text="beta" type="success" />

Released on November 10, 2021.

This hotfix release fixes an issue where the kubernetes agent would attempt to load a secret value and fail if it was not present.

See [the PR](https://github.com/PrefectHQ/prefect/pull/5131) for details.

## 0.15.8 <Badge text="beta" type="success" />

Released on November 10, 2021.

### Features

- Add support for rich iCal style scheduling via RRules - [#4901](https://github.com/PrefectHQ/prefect/pull/4901)
- Add Google Cloud Vertex agent and run configuration - [#4989](https://github.com/PrefectHQ/prefect/pull/4989)

### Enhancements

- Allow `Azure` flow storage to overwrite existing blobs - [#5103](https://github.com/PrefectHQ/prefect/pull/5103)
- Provide option to specify a dockerignore when using Docker storage - [#4980](https://github.com/PrefectHQ/prefect/pull/4980)
- Add keep-alive connections for kubernetes client API connections - [#5066](https://github.com/PrefectHQ/prefect/pull/5066)
- Add `idempotency_key` to `create_flow_run` task - [#5125](https://github.com/PrefectHQ/prefect/pull/5125)
- Add `raise_final_state` to `wait_for_flow_run` task to reflect child flow run state - [#5129](https://github.com/PrefectHQ/prefect/pull/5129)

### Task Library

- Bump maximum `google-cloud-bigquery` version to support 2.x - [#5084](https://github.com/PrefectHQ/prefect/pull/5084)
- Add `Glob` task for collecting files in directories - [#5077](https://github.com/PrefectHQ/prefect/pull/5077) 
- Add `DbtCloudRunJob` task for triggering dbt cloud run jobs - [#5085](https://github.com/PrefectHQ/prefect/pull/5085)
- Added Kafka Tasks entry to website docs - [#5094](https://github.com/PrefectHQ/prefect/pull/5094)

### Fixes

- Update the `FlowView` to be more robust to serialized flow changes in the backend - [#5116](https://github.com/PrefectHQ/prefect/pull/5116)

### Deprecations

- Move artifacts functions to `prefect.backend.artifacts` - [#5117](https://github.com/PrefectHQ/prefect/pull/5117)

### Server

This release includes a Prefect Server update that updates an upstream dependency to fix a security vulnerability. See the [release changelog](https://github.com/PrefectHQ/server/blob/master/Changelog.md#november-09-2021-) for more details.

### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Bradley Axen](https://github.com/baxen)
- [Damien Ramunno-Johnson](https://github.com/damienrj)
- [Jonas Miederer](https://github.com/jonasmiederer)
- [Josh Wang](https;//github.com/wangjoshuah)
- [Nitay Joffe](https://github.com/nitay)
- [Timo S.](https://github.com/sti0)
- [Brett Naul](https://github.com/bnaul)

## 0.15.7 <Badge text="beta" type="success" />

Released on October 21, 2021.

### Enhancements

- Add flatten support to `apply_map` - [#4996](https://github.com/PrefectHQ/prefect/pull/4996)
- Add dask performance report to `DaskExecutor` - [#5032](https://github.com/PrefectHQ/prefect/pull/5032)
- Update git storage `repo` parameter to be optional if specifying `git_clone_url_secret_name` - [#5033](https://github.com/PrefectHQ/prefect/pull/5033)
- Add `task_run_name` to `prefect.context` - [#5055](https://github.com/PrefectHQ/prefect/pull/5055)

### Fixes

- Reduce rate limit related failures with the ECS agent - [#5059](https://github.com/PrefectHQ/prefect/pull/5059)

### Task Library

- Add `data` parameter to `SQLiteQuery` task - [#4981](https://github.com/PrefectHQ/prefect/pull/4981)
- Allow `EmailTask` to use insecure internal SMTP servers with `smtp_type="INSECURE"` - [#5012](https://github.com/PrefectHQ/prefect/pull/5012)
- Fix Databricks `run_id` mutation during task runs - [#4958](https://github.com/PrefectHQ/prefect/issues/4958)
- Add `manual` setting to `FivetranSyncTask` allowing retention of Fivetan scheduling -[#5065](https://github.com/PrefectHQ/prefect/pull/5065)

### Contributors

- [Daniel Saxton](https://github.com/dsaxton)
- [Emre Akgün](https://github.com/Fraznist)
- [Jessica Smith](https://github.com/NodeJSmith)

## 0.15.6 <Badge text="beta" type="success" />

Released on September 21, 2021.

### Enhancements

- Improve setting the Azure storage connection string - [#4955](https://github.com/PrefectHQ/prefect/pull/4955)
- Allow disabling retries for a task with `max_retries=0` when retries are globally configured - [#4971](https://github.com/PrefectHQ/prefect/pull/4971)

### Task Library

- Allow Exasol Tasks to handle Prefect Secrets directly - [#4436](https://github.com/PrefectHQ/prefect/pull/4436)
- Adding [Census](https://www.getcensus.com/) Syncs to the task library - [#4935](https://github.com/PrefectHQ/prefect/pull/4935)

### Fixes

- Fix bug where `LocalDaskExecutor` did not respond to a `PrefectSignal` - [#4924](https://github.com/PrefectHQ/prefect/pull/4924)
- Fix `PostgresFetch` with headers for one row - [#4968](https://github.com/PrefectHQ/prefect/pull/4968)
- Fix bug where `apply_map` could create acyclic flows - [#4970](https://github.com/PrefectHQ/prefect/pull/4970)

### Contributors

- [Donny Flynn](https://github.com/dflynn20)
- [Noah Holm](https://github.com/noppaz)
- [Timo S.](https://github.com/sti0)

## 0.15.5 <Badge text="beta" type="success" />

Released on September 2, 2021.

### Features

- Python 3.9 docker images are now published - [#4896](https://github.com/PrefectHQ/prefect/pull/4896)

### Enhancements

- Add `--expose` flag to `prefect server` cli to make the Core server and UI listen to all interfaces - [#4821](https://github.com/PrefectHQ/prefect/pull/4821)
- Pass existing/local environment variables to agentless flow runs - [#4917](https://github.com/PrefectHQ/prefect/pull/4917)
- Add `--idempotency-key` to `prefect run` - [#4928](https://github.com/PrefectHQ/prefect/pull/4928)
- Add support for larger flow registration calls - [#4930](https://github.com/PrefectHQ/prefect/pull/4930)
- Ignore schedules by default for CLI flow runs and add flag to run based on schedule for local only runs [#4817](https://github.com/PrefectHQ/prefect/pull/4817)

### Task Library

- Feature: Added `SnowflakeQueryFromFile` task [#3744](https://github.com/PrefectHQ/prefect/pull/4363)
- Enhancement: Log boto exceptions encountered in the in AWS `BatchSubmit` task - [#4771](https://github.com/PrefectHQ/prefect/pull/4771)
- Breaking: Legacy Dremio authentication has been updated to the new pattern in `DremioFetch` - [#4872](https://github.com/PrefectHQ/prefect/pull/4872)
- Fix: Use runtime arguments over init arguments instead of ignoring them for MySQL Tasks - [#4907](https://github.com/PrefectHQ/prefect/pull/4907)
### Fixes

- Adjust log limits to match backend logic for better UX - [#4900](https://github.com/PrefectHQ/prefect/pull/4900)
- Fix use of `marshmallow.fields.Dict` to use `keys` as a kwarg rather than `key`. - [#4903](https://github.com/PrefectHQ/prefect/pull/4903)
- API server settings are passed correctly to task workers when using Prefect Server - [#4914](https://github.com/PrefectHQ/prefect/pull/4914)
- Do not attempt attempt to set `host_gateway` if using an unsupported Docker Engine version - [#4809](https://github.com/PrefectHQ/prefect/pull/4809)
- Ignore jobs without a `flow_run_id` label in `KubernetesAgent.manage_jobs` - [#4934](https://github.com/PrefectHQ/prefect/pull/4934)
### Breaking Changes

- Services run by `prefect server` cli are now local by default (listen to localhost instead of 0.0.0.0); use `--expose` if you want to connect from a remote location - [#4821](https://github.com/PrefectHQ/prefect/pull/4821)
- The changes in flow registration require Prefect Server 2021.09.02. Prefect Server will need to be upgraded before flows can be registered from this version - [#4930](https://github.com/PrefectHQ/prefect/pull/4930)

### Contributors

- [Deepyaman Datta](https://github.com/deepyaman)
- [Henri Hannetel](https://github.com/HenriTEL)
- [Johnny Tirado](https://github.com/jclocks)
- [Kathryn Klarich](https://github.com/klarich)
- [Tenzin Choedak](https://github.com/tchoedak)
- [Vincent Xue](https://github.com/xuevin)

## 0.15.4 <Badge text="beta" type="success" />

Released on August 17, 2021.

### Docs

- Add a getting started section with a quick start guide for both core and orchestration sections - [#4734](https://github.com/PrefectHQ/prefect/pull/4734)
### Enhancements

- Expose Snowflake cursor type to SnowflakeQuery task arguments [#4786](https://github.com/PrefectHQ/prefect/issues/4786)
- Add ability to use threaded flow heartbeats - [#4844](https://github.com/PrefectHQ/prefect/pull/4844)
- Improve behavior when API rate limits are encountered - [#4852](https://github.com/PrefectHQ/prefect/pull/4852)
- Allow custom git clone url for `Git` storage - [#4870](https://github.com/PrefectHQ/cloud/pull/4870)
- Add `on_worker_status_changed` callback to the `DaskExecutor` - [#4874](https://github.com/PrefectHQ/prefect/pull/4874)
- Add `--agent-config-id` to `prefect agent <kubernetes|local> install` - [#4876](https://github.com/PrefectHQ/prefect/pull/4876)

### Task Library

- Add new prometheus task to push to gateway - [#4623](https://github.com/PrefectHQ/prefect/pull/4623)

### Fixes

- Fix binding of named volumes to flow containers with Docker agent - [#4800](https://github.com/PrefectHQ/prefect/pull/4800)
- Fix `ImportError` typo in dropbox module - [#4855](https://github.com/PrefectHQ/prefect/pull/4855)
- Fix default safe char for gitlab storage repo path - [#4828](https://github.com/PrefectHQ/prefect/pull/4828)

### Contributors

- [Austen Bouza](https://github.com/austen-bouza)
- [David Zucker](https://github.com/davzucky)
- [Jacob Dawang](https://github.com/jdawang)
- [Tom Forbes](https://github.com/orf)
- [Mat](https://github.com/matmiad)

## 0.15.3 <Badge text="beta" type="success" />

Released on July 27, 2021.

### Enhancements

- Add new `evaluation_parameters` parameter to `RunGreatExpectationsValidation` task - [#4798](https://github.com/PrefectHQ/prefect/pull/4798)

### Fixes

- Fix `create_flow_run` compatibility with auth tokens - [#4801](https://github.com/PrefectHQ/prefect/pull/4801)
- Fix auto-quoting for strings that begin with numeric characters - [#4802](https://github.com/PrefectHQ/prefect/pull/4802)

### Contributors

- [Michal Zawadzki](https://github.com/trymzet)

## 0.15.2 <Badge text="beta" type="success" />

Released on July 20, 2021.

### Enhancements

- Allow CLI registration of flows without starting their schedule `prefect register --no-schedule` - [#4752](https://github.com/PrefectHQ/prefect/pull/4752)
- Add `host_config` to `DockerRun` to expose deeper settings for Docker flow runs - [#4733](https://github.com/PrefectHQ/prefect/issues/4773)
- Enable loading additional repository files with `Git` storage - [#4767](https://github.com/PrefectHQ/prefect/pull/4767)
- Update flow run heartbeats to be robust to exceptions - [#4736](https://github.com/PrefectHQ/prefect/pull/4736)
- Allow `prefect build/register` paths to contain globs for recursion - [#4761](https://github.com/PrefectHQ/prefect/pull/4761)

### Fixes

- Fix duplicate task runs in `FlowRunView.get_all_task_runs` - [#4774](https://github.com/PrefectHQ/prefect/pull/4774)
- Fix zombie processes from exited heartbeats - [#4733](https://github.com/PrefectHQ/prefect/pull/4733)
- Missing `auth_file` directory is created when saving credentials - [#4792](https://github.com/PrefectHQ/prefect/pull/4792)

### Task Library

- Add `VaultSecret` task for retrieving secrets from private Vault instances - [#4656](https://github.com/PrefectHQ/prefect/pull/4656)

### Contributors

- [Gabriel Montañola](https://github.com/gmontanola)
- [Nelson Griffiths](https://github.com/ngriffiths13)
- [Pawel Janowski](https://github.com/pjanowski)
- [Yueh Han Huang](https://github.com/bojne)
- [Chris Ottinger](https://github.com/datwiz)

## 0.15.1 <Badge text="beta" type="success" />

Released on July 12, 2021.

### Enhancements

- Add documentation for querying role and membership info - [#4721](https://github.com/PrefectHQ/prefect/pull/4721)
- Checkpoint task results when `SUCCESS` is raised - [#4744](https://github.com/PrefectHQ/prefect/pull/4744)

### Fixes

- Fix loading of `PREFECT__CLOUD__API_KEY` environment variable when starting agents - [#4751](https://github.com/PrefectHQ/prefect/pull/4751)
- Fix bug where the tenant could not be inferred during flow runs while using token auth - [#4758](https://github.com/PrefectHQ/prefect/pull/4758)
- Fix bug where an agent using token auth could clear the tenant from disk - [#4759](https://github.com/PrefectHQ/prefect/pull/4759)

## 0.15.0 <Badge text="beta" type="success" />

Released on July 1, 2021.

### Features

- Add objects for inspecting flows, flow runs, and task runs without writing queries - [#4426](https://github.com/PrefectHQ/prefect/pull/4426)
- Rehaul `prefect run` CLI for executing flows locally and with agents - [#4463](https://github.com/PrefectHQ/prefect/pull/4463)
- Add flow run tasks to simplify flow run result passing - [#4563](https://github.com/PrefectHQ/prefect/pull/4563)
- Add agentless execution for flow runs - [#4589](https://github.com/PrefectHQ/prefect/pull/4589)
- Add `prefect auth create-key` to create API keys - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Add `prefect auth list-keys` to list API key metadata - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Add `prefect auth revoke-key` to revoke an API key - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Add `prefect auth status` command to see the state of your authentication - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)

### Enhancements

- Improve flow run documentation with new dedicated section - [#4492](https://github.com/PrefectHQ/prefect/pull/4492)
- Update `Client` to support API keys - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Add API key support to `prefect auth login/logout/switch-tenants` - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- API keys can be configured in the Prefect config - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Change SendGrid `SendEmail` task to use secret value - [#4669](https://github.com/PrefectHQ/prefect/pull/4669)
- Add `TenantView` for retrieval of tenant information - [#4676](https://github.com/PrefectHQ/prefect/pull/4676)
- Add custom rbac documentation - [#4696](https://github.com/PrefectHQ/prefect/pull/4696)
- Exit with non-zero status on flow run failure when watched - [#4709](https://github.com/PrefectHQ/prefect/pull/4709)
- Display return code on local agent flow process failure - [#4715](https://github.com/PrefectHQ/prefect/pull/4715)

### Task Library

- Add `KafkaBatchConsume` and `KafkaBatchProduce` tasks - [#4533](https://github.com/PrefectHQ/prefect/pull/4533)

### Fixes

- Fix cleanup issue with `Git` storage on Windows - [#4665](https://github.com/PrefectHQ/prefect/pull/4665)
- Pass API keys as tokens for compatibility when creating flow run environments - [#4683](https://github.com/PrefectHQ/prefect/pull/4683)
- Fix missing event timestamp attribute errors in K8s agent - [#4693](https://github.com/PrefectHQ/prefect/pull/4693)
- Fix backwards compatibility for flows without a `terminal_state_handler` - [#4695](https://github.com/PrefectHQ/prefect/pull/4695)
- Raise a better exception when a task run result type is not set in `TaskRunView.get_result()` - [#4708](https://github.com/PrefectHQ/prefect/pull/4708)

### Deprecations

- Deprecate `prefect auth create-token` - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Deprecate `prefect auth list-tokens` - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Deprecate `prefect auth revoke-token` - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- Deprecate setting auth tokens in the Prefect config - [#4643](https://github.com/PrefectHQ/prefect/pull/4643)
- `prefect.utilities.exceptions` has been deprecated in favor of `prefect.exceptions` - [#4664](https://github.com/PrefectHQ/prefect/pull/4664)

### Breaking Changes

- Remove deprecated `prefect.environment.storage` module
- Remove deprecated `DockerAgent` kwarg `network`
- Remove deprecated `kubernetes.ResourceManager` class
- Remove deprecated `prefect agent start/install <agent-type>` commands
- Remove deprecated `prefect agent local start` flag `--storage-labels`
- Remove deprecated `DroboxDownload` task kwarg `access_token_secret`
- Remove deprecated `GCS...` tasks kwarg `encryption_key_secret`
- Remove deprecated `prefect.tasks.google` module
- Remove deprecated `prefect.tasks.secret.Secret` class
- Remove deprecated `Scheduler` serializers for Prefect <0.6.0
- Remove deprecated `RunGreatExpectionsCheckpoint` task
- Remove deprecated `OneTimeSchedule` and `UnionSchedule` classes
- Remove deprecated flow run tasks ending in `Task`
- Remove deprecated prefect.utilities.tasks.unmapped; moved to `prefect.utilities.edges.unmapped`
- Prefect state signals now inherit from `BaseException` to prevent accidental capture - [#4664](https://github.com/PrefectHQ/prefect/pull/4664)
- `TaskTimeoutError` has been replaced with `TaskTimeoutSignal` - [#4664](https://github.com/PrefectHQ/prefect/pull/4664)
- `VersionLockError` has been replaced with `VersionLockMismatchSignal` - [#4664](https://github.com/PrefectHQ/prefect/pull/4664)

### Contributors

- [Stéphan Taljaard](https://github.com/taljaards)
- [Tenzin Choedak](https://github.com/tchoedak)

## 0.14.22 <Badge text="beta" type="success" />

Released on June 15, 2021.

### Enhancements

- Use `functools.update_wrapper` for `FunctionTask` - [#4608](https://github.com/PrefectHQ/prefect/pull/4608)
- Add ability to merge reference tasks when combining two flows - [#4644](https://github.com/PrefectHQ/prefect/pull/4644)
- Add client side check for key value size - [#4655](https://github.com/PrefectHQ/prefect/pull/4655)
- Ensure stack traces are included in logs during task run exceptions - [#4657](https://github.com/PrefectHQ/prefect/pull/4657)
- Add `poll_interval` parameter to `StartFlowRun` to define the polling interval when waiting for the flow run to finish - [#4641](https://github.com/PrefectHQ/prefect/pull/4641)
- Add ability to set task timeouts with `timedelta` objects - [#4619](https://github.com/PrefectHQ/prefect/pull/4619)

### Fixes

- Add ssh documentation - [#4539](https://github.com/PrefectHQ/prefect/pull/4539)

### Contributors

- [Pawel Janowski, Recursion](https://github.com/pjanowski)
- [Peter Roelants](https://github.com/peterroelants)

## 0.14.21 <Badge text="beta" type="success" />

Released on June 2, 2021.

### Features

- Add interface for backend key-value metadata store - [#4499](https://github.com/PrefectHQ/prefect/pull/4499)

### Enhancements

- Keep intermediate docker layers when using Docker Storage to improve caching - [#4584](https://github.com/PrefectHQ/prefect/pull/4584)

### Fixes

- Fix possible race condition in `LocalResult` directory creation - [#4587](https://github.com/PrefectHQ/prefect/pull/4587)
- Use absolute paths when registering flows in `prefect register` - [#4593](https://github.com/PrefectHQ/prefect/pull/4593)
- Propagate storage labels (e.g. hostname label on `Local` storage) when registering flows with `prefect register` - [#4593](https://github.com/PrefectHQ/prefect/pull/4593)
- Fix small-flow parallelism issues with multiprocess `LocalDaskExecutor` - [#4602](https://github.com/PrefectHQ/prefect/pull/4602)
- Cleanly handle unpicklable exceptions in tasks - [#4605](https://github.com/PrefectHQ/prefect/pull/4605)

### Contributors

- [Tom Forbes](https://github.com/orf)

## 0.14.20 <Badge text="beta" type="success" />

Released on May 25, 2021.

### Enhancements

- Refactor `Agent` base class for readability - [#4341](https://github.com/PrefectHQ/prefect/pull/4341)
- Display the agent config id on agent startup if set - [#4524](https://github.com/PrefectHQ/prefect/pull/4524)
- Add debug logs during agent auth verification - [#4547](https://github.com/PrefectHQ/prefect/pull/4547)
- Sending logs to Cloud can be globally disabled via config in addition to the agent flag - [#4487](https://github.com/PrefectHQ/prefect/pull/4487)

### Task Library

- Enable sending attachments with emails in the `EmailTask` - [#4457](https://github.com/PrefectHQ/prefect/pull/4457)
- Add Google Cloud Platform `GCPSecret` task - [#4561](https://github.com/PrefectHQ/prefect/pull/4561)

### Fixes

- Fix `import_object` handling of submodules that are not attributes - [#4513](https://github.com/PrefectHQ/prefect/pull/4513)
- Fix `DockerStorage` building with python slim image - [#4523](https://github.com/PrefectHQ/prefect/pull/4523)
- Gracefully handle events with missing timestamps in K8s agent - [#4544](https://github.com/PrefectHQ/prefect/pull/4544)
- Fix bug where agent uses originally scheduled start time instead of latest state time - [#4568](https://github.com/PrefectHQ/prefect/pull/4568)

### Deprecations

- `logging.log_to_cloud` has been deprecated in favor of `cloud.send_flow_run_logs` - [#4487](https://github.com/PrefectHQ/prefect/pull/4487)

### Contributors

- [Stéphan Taljaard](https://github.com/taljaards)
- [Thomas Heyenbrock](https://github.com/thomasheyenbrock)

## 0.14.19 <Badge text="beta" type="success" />

Released on May 11, 2021 as a hotfix for 0.14.18

### Fixes

- Fix docker container name error while using docker agents - [#4511](https://github.com/PrefectHQ/prefect/pull/4511)

## 0.14.18 <Badge text="beta" type="success" />

Released on May 11, 2021.

### Enhancements

- Add an `image_pull_policy` kwarg to `KubernetesRun` - [#4462](https://github.com/PrefectHQ/prefect/pull/4462)
- Allow `prefect build/register --module` to accept full import path to flow - [#4468](https://github.com/PrefectHQ/prefect/pull/4468)
- Add `hello world` flow to prefect module - [#4470](https://github.com/PrefectHQ/prefect/pull/4470)
- Set docker container names to flow run names when running with the docker agent - [#4485](https://github.com/PrefectHQ/prefect/pull/4485)

### Task Library

- Add basic implementation of `SendGrid` to Task Library - [#4450](https://github.com/PrefectHQ/prefect/pull/4450)
- Log link to flow run in `StartFlowRun` - [#4458](https://github.com/PrefectHQ/prefect/pull/4458)
- Allow passing in `io.BytesIO` to `GCSUpload` - [#4482](https://github.com/PrefectHQ/prefect/pull/4482)

### Fixes

- Fix logging errors within `BigQuery` task - [#4419](https://github.com/PrefectHQ/prefect/pull/4419)
- Remove unnecessary docker interface detection in Docker agent - [#4446](https://github.com/PrefectHQ/prefect/pull/4446)
- Upgrade `kubernetes` package requirement upper limit - [#4452](https://github.com/PrefectHQ/prefect/pull/4452)
- Fix Prefect server startup check for custom server port - [#4501](https://github.com/PrefectHQ/prefect/pull/4501)

### Contributors

- [Brett Naul](https://github.com/bnaul)
- [Joël Luijmes](https://github.com/joelluijmes)
- [Stéphan Taljaard](https://github.com/taljaards)
- [Zach Schumacher](https://github.com/zschumacher)

## 0.14.17 <Badge text="beta" type="success" />

Released on April 27, 2021.

### Features

- Add git storage - [#4418](https://github.com/PrefectHQ/prefect/pull/4418)

### Enhancements

- Add test coverage for threaded `LocalDaskExecutor` timeouts - [#4217](https://github.com/PrefectHQ/prefect/pull/4217)
- Add environment variable support to UniversalRunConfig - [#4383](https://github.com/PrefectHQ/prefect/pull/4383)
- Adds column name fetching to PostgresFetch task - [#4414](https://github.com/PrefectHQ/prefect/pull/4414)
- Allow external Postgres with `prefect server start` command - [#4424](https://github.com/PrefectHQ/prefect/pull/4424)

### Fixes

- Pass reference tasks states instead of task states to terminal_state_handler - [#4409](https://github.com/PrefectHQ/prefect/pull/4409)
- Check for AWS_RETRY_MODE variable before setting default in `ECSAgent` - [#4417](https://github.com/PrefectHQ/prefect/pull/4417)
- Fixed bug from Flow.copy() not copying the slugs dictionary - [#4435](https://github.com/PrefectHQ/prefect/pull/4435)
- Fix compatibility with PyGithub >= 1.55 - [#4440](https://github.com/PrefectHQ/prefect/pull/4440)

### Contributors

- [Ben Fogelson](https://github.com/benfogelson)
- [Gabriel Montañola](https://github.com/gmontanola)

## 0.14.16 <Badge text="beta" type="success" />

Released on April 14, 2021.

### Enhancements

- Added support for Bitbucket cloud into Bitbucket storage class [#4318](https://github.com/PrefectHQ/prefect/issues/4318)
- Update docs for API keys - [#4313](https://github.com/PrefectHQ/prefect/pull/4313)
- Add option to disable the deletion of finished Prefect jobs in the Kubernetes agent - [#4351](https://github.com/PrefectHQ/prefect/pull/4351)
- Improve messaging when a flow is skipped during registration - [#4373](https://github.com/PrefectHQ/prefect/pull/4373)
- Display a more helpful error when calling a task outside a flow context - [#4374](https://github.com/PrefectHQ/prefect/pull/4374)
- Lower required docker-compose version and add note to docs - [#4396](https://github.com/PrefectHQ/prefect/pull/4396)
- Increase healthcheck intervals for Prefect Server - [#4396](https://github.com/PrefectHQ/prefect/pull/4396)
- Allow the `ShellTask` to be used on win32 - [#4397](https://github.com/PrefectHQ/prefect/pull/4397)

### Fixes

- Fix ShellTask docstring - [#4360](https://github.com/PrefectHQ/prefect/pull/4360)
- Fix incorrect unused task tracking - [#4368](https://github.com/PrefectHQ/prefect/pull/4368)
- Add error handling to timeouts that fail during result pickling or passing - [#4384](https://github.com/PrefectHQ/prefect/pull/4384)

### Contributors

- [Jonathan Wright](https://github.com/wrightjonathan)

## 0.14.15 <Badge text="beta" type="success" />

Released on April 5, 2021.

### Enhancements

- Add terminal flow state handler override  - [#4198](https://github.com/PrefectHQ/prefect/issues/4198)
- When manually set, `prefect.context.date` will be used to determine dependent values - [#4295](https://github.com/PrefectHQ/prefect/pull/4295)
- `prefect.context.date` will be cast to a `DateTime` object if given a parsable string - [#4295](https://github.com/PrefectHQ/prefect/pull/4295)
- Expand logging for `DaskExecutor`, including the cluster dashboard address (if available) - [#4321](https://github.com/PrefectHQ/prefect/pull/4321)
- Add ability to stream ShellTask logs with level INFO - [#4322](https://github.com/PrefectHQ/prefect/pull/4322)
- Add architecture diagram to docs - [#4187](https://github.com/PrefectHQ/prefect/issues/4187)
- Speed up flow validation logic - [#4347](https://github.com/PrefectHQ/prefect/pull/4347)
- Pin dask upper package versions - [#4350](https://github.com/PrefectHQ/prefect/pull/4350)

### Task Library

- Add first basic implementation of [soda-sql](https://github.com/sodadata/soda-sql) scan task
- Add new task KubernetesSecret - [#4307](https://github.com/PrefectHQ/prefect/pull/4307)

### Fixes

- Fix `DatabricksRunNow` task attribute override behavior - [#4309](https://github.com/PrefectHQ/prefect/pull/4309)
- Use default flow labels when triggering flow runs from CLI - [#4316](https://github.com/PrefectHQ/prefect/pull/4316)
- Improve ECS agent error messages, and fix bug that prevented using ECS agent on Fargate with ECR - [#4325](https://github.com/PrefectHQ/prefect/pull/4325)
- Support imports from local directory when registering/building flows via CLI - [#4332](https://github.com/PrefectHQ/prefect/pull/4332)
- Speedup flushing of logs to cloud/server on flow run shutdown, avoiding lost logs on platforms that SIGKILL the process after a short period - [#4334](https://github.com/PrefectHQ/prefect/pull/4334)

### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [David Zucker](https://github.com/davzucky)
- [Greg Lu](https://github.com/greglu)
- [James Lamb](https://github.com/jameslamb)
- [Sean Talia](https://github.com/TaliaSRTR)

## 0.14.14 <Badge text="beta" type="success" />

Released on March 25, 2021.

### Task Library

- Ensures Snowflake Query Task output is serializable [#3744](https://github.com/PrefectHQ/prefect/issues/3744)

### Fixes

- Always load task run info prior to running a task - [#4296](https://github.com/PrefectHQ/prefect/pull/4296)

## 0.14.13 <Badge text="beta" type="success" />

Released on March 24, 2021.

### Features

- Add new improved `prefect register` CLI command. This command supports registering multiple flows at once (through multiple file paths or directories), and also includes a new `--watch` flag for watching files and automatically re-registering upon changes. - [#4256](https://github.com/PrefectHQ/prefect/pull/4256)
- New `prefect build` CLI command for building flows. Artifacts produced by this command can then be used by `prefect register` to register flows without requiring the source. - [#4282](https://github.com/PrefectHQ/prefect/pull/4282)

### Enhancements

- Use explicit exception chaining [#3306](https://github.com/PrefectHQ/prefect/issues/3306)
- Add `as_bytes` option to `S3Download` task - [#4238](https://github.com/PrefectHQ/prefect/pull/4238)
- Improve error message when a loaded flow doesn't match the version stored in Prefect Cloud/Server - [#4259](https://github.com/PrefectHQ/prefect/pull/4259)
- Support setting flow run labels from cli - [#4266](https://github.com/PrefectHQ/prefect/pull/4266)
- Support setting default `image` in `--job-template`/`--task-definition` in Kubernetes/ECS agents - [#4270](https://github.com/PrefectHQ/prefect/pull/4270)

### Task Library

- Adds logging of cell outputs to Jupyter task - [#4265] (https://github.com/PrefectHQ/prefect/issues/4265)
- Add `user` and `password` as runtime parameters to Exasol tasks - [#4268](https://github.com/PrefectHQ/prefect/pull/4268)

### Fixes

- Fix bug where sometimes the global `prefect.context` wouldn't be respected during a flow run - [#4287](https://github.com/PrefectHQ/prefect/pull/4287)

### Deprecations

- Deprecate the old `prefect register flow` CLI command in favor of `prefect register` - [#4256](https://github.com/PrefectHQ/prefect/pull/4256)
- Deprecate `user` and `password` arguments to Exasol task constructors in favor of runtime parameters - [#4268](https://github.com/PrefectHQ/prefect/pull/4268)

### Contributors

- [Abid Ahmad](https://github.com/abid1998)
- [Alexandr N. Zamaraev](https://github.com/tonal)
- [Jacob Hayes](https://github.com/JacobHayes)
- [Kevin Kho](https://github.com/kvnkho)
- [Timo S.](https://github.com/sti0)

## 0.14.12 <Badge text="beta" type="success" />

Released on March 10, 2021.

### Enhancements

- Upgrade hasura to 1.3.3 in Prefect Server - [#4126](https://github.com/PrefectHQ/prefect/pull/4126)
- Add `--docker-client-timeout` flag to docker agent, for configuring the timeout for all docker API requests - [#4232](https://github.com/PrefectHQ/prefect/pull/4232)
- Make `--slug` flag optional in `prefect server create-tenant` - [#4240](https://github.com/PrefectHQ/prefect/pull/4240)

### Task Library

- Adds new filesystem `Copy` and `Remove` tasks - [#4202](https://github.com/PrefectHQ/prefect/pull/4202)

### Fixes

- Don't forward `nout` to mapped tasks - [#4206](https://github.com/PrefectHQ/prefect/pull/4206)
- Move `command`, `environment`, `cpu`, `memory`, `execution_role_arn`, and `task_role_arn` configuration for ECS tasks from definition time to run time in the ECS agent - [#4211](https://github.com/PrefectHQ/prefect/pull/4211)
- Register (and deregister) a new task definition for every flow run in ECS agent - [#4211](https://github.com/PrefectHQ/prefect/pull/4211)
- Fix `Task` signature generation in the presence of with variadic kwargs - [#4235](https://github.com/PrefectHQ/prefect/pull/4235)
- Ensure `Flow` is serializable using `pickle` - [#4209](https://github.com/PrefectHQ/prefect/pull/4209)

### Contributors

- [Ben Fogelson](https://github.com/benfogelson)
- [Marwan S.](https://github.com/marwan116)
- [Timo S.](https://github.com/sti0)

## 0.14.11 <Badge text="beta" type="success" />

Released on March 3, 2021.

### Features

- Add command `prefect server config` to output configured docker-compose yaml - [#4176](https://github.com/PrefectHQ/prefect/pull/4176)

### Enhancements

- Add `project_name` and `project_id` to context during Cloud/Server flow runs - [#4083](https://github.com/PrefectHQ/prefect/pull/4083)
- Better error message when flow not found in file - [#4182](https://github.com/PrefectHQ/prefect/pull/4182)
- Improve generated names for `GetItem` tasks - [#4183](https://github.com/PrefectHQ/prefect/pull/4183)
- Add `base_url` option to `GitHub` storage - [#4194](https://github.com/PrefectHQ/prefect/pull/4194)

### Task Library

- Add filehandling tasks `Move`, `Unzip`, `Zip` - [#4131](https://github.com/PrefectHQ/prefect/pull/4139)
- Add `msg_plain`, `email_to_cc`, and `email_to_bcc` options to `EmailTask` - [#4157](https://github.com/PrefectHQ/prefect/pull/4157)
- Add `jar_params` option to `DatabricksRunNow` task - [#4157](https://github.com/PrefectHQ/prefect/pull/4178)

### Fixes

- Make task slug generation robust to modifying existing task names - [#4189](https://github.com/PrefectHQ/prefect/pull/4189)
- Forward `client_options` to `S3Result` from `S3` storage - [#4195](https://github.com/PrefectHQ/prefect/pull/4195)

### Contributors

- [David Zucker](https://github.com/davzucky)
- [Jacob Hayes](https://github.com/JacobHayes)
- [Joël Luijmes](https://github.com/joelluijmes)
- [Timo S.](https://github.com/sti0)
- [Yogi Patel](https://github.com/ypatel-whitepages)

## 0.14.10 <Badge text="beta" type="success" />

Released on February 23, 2021.

### Fixes

- Dynamically import compression libraries for `CompressedSerializer` - [#4150](https://github.com/PrefectHQ/prefect/pull/4150)
- Support passing environment variables containing `=` through agent CLI `--env` flag - [#4160](https://github.com/PrefectHQ/prefect/pull/4160)

## 0.14.9 <Badge text="beta" type="success" />

Released on February 16, 2021.

### Enhancements

- Add `CompressedSerializer` class - [#4063](https://github.com/PrefectHQ/prefect/pull/4063)
- Allow `Client` timeout seconds to be configurable through configuration - [#4118](https://github.com/PrefectHQ/prefect/issues/4118)

### Task Library

- Update `FilterTask` to allow logging the filtered output via a function - [#4121](https://github.com/PrefectHQ/prefect/pull/4121)
- Add `FivetranSyncTask`, to manage your [Fivetran](https://fivetran.com) connector sync process - [#4116](https://github.com/PrefectHQ/prefect/pull/4116)

### Fixes

- Reduce the number of boto3 clients created across Prefect when interacting with AWS services - [#4115](https://github.com/PrefectHQ/prefect/pull/4115)

### Deprecations

- Deprecate the `use_session` argument in all AWS-related components - [#4115](https://github.com/PrefectHQ/prefect/pull/4115)

### Contributors

- [Amanda Wee](https://github.com/amanda-wee)
- [Andrew Hannigan](https://github.com/AndrewHannigan)
- [Craig Wright](https://github.com/crw)
- [Nick Acosta](https://github.com/PubChimps)
- [Timo S.](https://github.com/sti0)

## 0.14.8 <Badge text="beta" type="success" />

Released on February 11, 2021.

### Enhancements

- Add option to provide version group ID to `prefect run flow` CLI command - [#4100](https://github.com/PrefectHQ/prefect/pull/4100)

### Fixes

- Fix bug in agent healthcheck route that was introduced in 0.14.7 - [#4109](https://github.com/PrefectHQ/prefect/pull/4109)

## 0.14.7 <Badge text="beta" type="success" />

Released on February 10, 2021.

### Enhancements

- Support multiple docker networks with Docker Agent - [#3986](https://github.com/PrefectHQ/prefect/issues/3986)
- Add healthchecks to prefect server - [#4041](https://github.com/PrefectHQ/prefect/pull/4041)
- Raise custom `TimeoutError` for task timeouts to allow for more granular user control - [#4091](https://github.com/PrefectHQ/prefect/issues/4091)
- Add `access_token_secret` to `GitHub`, `GitLab`, and `Bitbucket` storage, making the Prefect secret containing an access token to these services configurable - [#4059](https://github.com/PrefectHQ/prefect/pull/4059)
- Add `--skip-if-flow-metadata-unchanged` to `prefect register flow` CLI command that avoids bumping flow version if flow metadata has not changed - [#4061](https://github.com/PrefectHQ/prefect/pull/4061)
- Add `--skip-if-exists` to `prefect create project` CLI command that safely skips if the project has already been created - [#4061](https://github.com/PrefectHQ/prefect/pull/4061)
- Add new `Module` storage class, for referencing flows importable from a Python module - [#4073](https://github.com/PrefectHQ/prefect/pull/4073)
- Drop resource limits from manifest generated using `prefect agent kubernetes install` - [#4077](https://github.com/PrefectHQ/prefect/pull/4077)

### Task Library

- Add new tasks for communication with an Exasol database - [#4044](https://github.com/PrefectHQ/prefect/pull/4044)

### Fixes

- Fix task decorator chaining by using `inspect.unwrap` instead of `__wrap__` - [#4053](https://github.com/PrefectHQ/prefect/pull/4053)
- Forward Prefect backend type to deployed flow runs, ensuring backend-specific logic functions properly - [#4076](https://github.com/PrefectHQ/prefect/pull/4076)
- Patch around bug in dask's multiprocessing scheduler introduced in Dask 2021.02.0 - [#4089](https://github.com/PrefectHQ/prefect/pull/4089)

### Deprecations

- Docker agent `network` kwarg deprecated in favor of `networks` - [#3986](https://github.com/PrefectHQ/prefect/issues/3986)

### Breaking Changes

- Remove unused `Storage.get_env_runner` method - [#4059](https://github.com/PrefectHQ/prefect/pull/4059)
- Remove private utilities in `prefect.utilities.git` - [#4059](https://github.com/PrefectHQ/prefect/pull/4059)

### Contributors

- [Alex P.](https://github.com/alexifm)
- [Marwan S.](https://github.com/marwan116)
- [Peter Roelants](https://github.com/peterroelants)
- [Timo S.](https://github.com/sti0)

## 0.14.6 <Badge text="beta" type="success" />

Released on February 2, 2021.

### Enhancements

- Add option to provide flow ID to `run flow` CLI command - [#4021](https://github.com/PrefectHQ/prefect/pull/4021)
- Flow name and project are no longer required options when calling `run flow` CLI command - [#4021](https://github.com/PrefectHQ/prefect/pull/4021)

### Task Library

- Add GCSBlobExists which checks for the existence of an object in a given GCS bucket - [#4025](https://github.com/PrefectHQ/prefect/pull/4025)
- Use boto3 session in `S3Upload` and `S3Download` tasks, to ensure thread-safe execution - [#3981](https://github.com/PrefectHQ/prefect/pull/3981)

### Fixes

- Fix issue with fixed duration Paused states not resuming properly - [#4031](https://github.com/PrefectHQ/prefect/issues/4031)

### Contributors

- [Gregory Roche](https://github.com/gregoryroche)

## 0.14.5 <Badge text="beta" type="success" />

Released on January 26, 2021.

### Enhancements

- S3 storage now logs `ETag`, `LastModified` timestamp, and `VersionId` (if present) when loading a flow - [#3995](https://github.com/PrefectHQ/prefect/pull/3995)
- `GitHub` storage now logs the commit sha used when loading a flow - [#3998](https://github.com/PrefectHQ/prefect/pull/3998)
- `GitHub` storage now loads from a repo's default branch, allowing default branch names other than 'master' - [#3998](https://github.com/PrefectHQ/prefect/pull/3998)
- Improve error message when Secrets are missing with Server - [#4003](https://github.com/PrefectHQ/prefect/pull/4003)
- Better error message when passing parameters to `StartFlowRun` constructor - [#4008](https://github.com/PrefectHQ/prefect/pull/4008)
- Add warning if user-defined class shadows an attribute used by the base class - [#4011](https://github.com/PrefectHQ/prefect/pull/4011)
- Add support for `EXTRA_PIP_PACKAGES` environment variable in `prefecthq/prefect` images, simplifying installation of dependencies during development - [#4013](https://github.com/PrefectHQ/prefect/pull/4013)
- Add execution role arn parameter to ecs run config and agent - [#4015](https://github.com/PrefectHQ/prefect/pull/4015)

### Task Library

- Add `ConnectGetNamespacedPodExec` task which runs an exec command in provided pod container - [#3991](https://github.com/PrefectHQ/prefect/pull/3991)
- Ensure connection secrets can be passed to Databricks tasks at runtime - [#4001](https://github.com/PrefectHQ/prefect/pull/4001)

### Fixes

- Fix Agent registration possibly skipping on server connection issues - [#3972](https://github.com/PrefectHQ/prefect/issues/3972)
- `GCSUpload` task now explicitely fails when ran on non-supported types - [#3978](https://github.com/PrefectHQ/prefect/pull/3978)
- Make logging to Prefect cloud more robust in the presence of errors or process shutdown - [#3989](https://github.com/PrefectHQ/prefect/pull/3989)
- Handle setting state for missing flow runs in Kubernetes agent resource management - [#4006](https://github.com/PrefectHQ/prefect/pull/4006)

### Contributors

- [Loïc Macherel](https://github.com/LoicEm)
- [Thomas Baldwin](https://github.com/baldwint)

## 0.14.4 <Badge text="beta" type="success" />

Released on January 19, 2021.

### Enhancements

- Retry on additional status codes - [#3959](https://github.com/PrefectHQ/prefect/pull/3959)
- Rerun secret tasks on flow-run restart - [#3977](https://github.com/PrefectHQ/prefect/pull/3977)

### Task Library

- Stream log output from Kubernetes RunNamespacedJob - [#3715](https://github.com/PrefectHQ/prefect/pull/3715)
- Add ReadNamespacedPodLogs which reads or streams logs from Kubernetes pod - [#3715](https://github.com/PrefectHQ/prefect/pull/3715)
- Add SQL Server task to query SQL Server databases - [#3958](https://github.com/PrefectHQ/prefect/pull/3958)
- Add chunking to GCP storage tasks - [#3968](https://github.com/PrefectHQ/prefect/pull/3968)

### Fixes

- Properly handle `NotImplementedError` exceptions raised by a result's serializer - [#3964](https://github.com/PrefectHQ/prefect/pull/3964)
- Fix support for storing multiple flows in a single script in storage - [#3969](https://github.com/PrefectHQ/prefect/pull/3969)
- Fix regression in `apply_map` which prevented use in `case`/`resource_manager` blocks - [#3975](https://github.com/PrefectHQ/prefect/pull/3975)

### Contributors

- [Joël Luijmes](https://github.com/joelluijmes)
- [Peyton Runyan](https://github.com/peytonrunyan/)
- [wangjoshuah](https://github.com/wangjoshuah)

## 0.14.3 <Badge text="beta" type="success" />

Released on January 13, 2021.

### Enhancements

- Better errors/warnings when flow fails to load in execution environment - [#3940](https://github.com/PrefectHQ/prefect/pull/3940)

### Task Library

- Add an Asana task to add tasks to an asana project - [#3935](https://github.com/PrefectHQ/prefect/pull/3935)

### Fixes

- Fix `prefect server start` failure when given a custom graphql host port - [#3933](https://github.com/PrefectHQ/prefect/pull/3933)
- Fix Kubernetes Agent attempting to report container info for failed pods when no container statuses are found - [#3941](https://github.com/PrefectHQ/prefect/pull/3941)
- Avoid race condition when creating task run artifacts for mapped tasks - [#3953](https://github.com/PrefectHQ/prefect/pull/3953)
- Propogate agent labels info to k8s flow runs, to match other agent behavior - [#3954](https://github.com/PrefectHQ/prefect/pull/3954)

## 0.14.2 <Badge text="beta" type="success" />

Released on January 6, 2021.

### Features

- Support for specifying `run_config` for an individual flow run - [#3903](https://github.com/PrefectHQ/prefect/pull/3903)
- Allow the usage of a `profile_name` on `get_boto_client` - [#3916](https://github.com/PrefectHQ/prefect/pull/3916)

### Enhancements

- Support executing Prefect agents/flows without having the `prefect` CLI on path - [#3918](https://github.com/PrefectHQ/prefect/pull/3918)

### Task Library

- Add support for specifying a `run_config` in `StartFlowRun` - [#3903](https://github.com/PrefectHQ/prefect/pull/3903)
- Task to add Trello card for task library - [#3910](https://github.com/PrefectHQ/prefect/pull/3910)

### Fixes

- Remove unused `description` field on `Task` serializer - [#3917](https://github.com/PrefectHQ/prefect/pull/3917)
- Fix edge case in `apply_map` that resulted in cycles in the `Flow` graph - [#3920](https://github.com/PrefectHQ/prefect/pull/3920)
- Support storing multiple local flows with the same name when using `Local` storage - [#3923](https://github.com/PrefectHQ/prefect/pull/3923)
- Fix bug in `prefect.context` contextmanager that resulted in context fields reverting to their initially configured values - [#3924](https://github.com/PrefectHQ/prefect/pull/3924)

### Contributors

- [Albert Franzi](https://github.com/afranzi)

## 0.14.1 <Badge text="beta" type="success" />

Released on December 29, 2020.

### Enhancements

- Make `setup` method optional for `resource_manager` tasks - [#3869](https://github.com/PrefectHQ/prefect/pull/3869)
- Add labels to all containers managed by the docker agent - [#3893](https://github.com/PrefectHQ/prefect/pull/3893)
- Add `prefect server stop` command for stopping the server - [#3899](https://github.com/PrefectHQ/prefect/pull/3899)
- Add `--detach` to `prefect server start` for running the server in the background - [#3899](https://github.com/PrefectHQ/prefect/pull/3899)

### Fixes

- Add support for `google-cloud-storage` < 1.31.0 - [#3875](https://github.com/PrefectHQ/prefect/pull/3875)
- Fix use of `imagePullSecrets`/`serviceAccountName` in k8s agent - [#3884](https://github.com/PrefectHQ/prefect/pull/3884)
- Fix `read_bytes_from_path` to work properly with S3 - [#3885](https://github.com/PrefectHQ/prefect/pull/3885)
- Change default `idempotency_key` in `StartFlowRun` to use `task_run_id` instead of `flow_run_id` - [#3892](https://github.com/PrefectHQ/prefect/pull/3892)

## 0.14.0 <Badge text="beta" type="success" />

Released on December 16, 2020.

### Features

- New flow run configuration system based on `RunConfig` types, see [here](https://docs.prefect.io/orchestration/flow_config/overview.html) for more info

### Enhancements

- Kubernetes Agent now reports events for pending pods created by prefect jobs - [#3783](https://github.com/PrefectHQ/prefect/pull/3783)
- Using `--rbac` for Kubernetes Agent install command now includes the `events` resource - [#3783](https://github.com/PrefectHQ/prefect/pull/3783)
- Add orchestration-based dependencies to the `prefecthq/prefect` Docker image - [#3804](https://github.com/PrefectHQ/prefect/pull/3804)
- Add a slimmed down `prefecthq/prefect:core` Docker image that only contains base dependencies - [#3804](https://github.com/PrefectHQ/prefect/pull/3804)
- Docker storage now installs all orchestration-based dependencies when using default image - [#3804](https://github.com/PrefectHQ/prefect/pull/3804)
- Add warning on flow registration if `flow.executor` is set but the flow is using the legacy `flow.environment` configuration system - [#3808](https://github.com/PrefectHQ/prefect/pull/3808)
- Echoing prefect config file as JSON to be able to parse it with jq in the terminal - [#3818](https://github.com/PrefectHQ/prefect/pull/3818)
- Produce artifact for RunGreatExpectationsValidation even if validation fails - [#3829](https://github.com/PrefectHQ/prefect/pull/3829)
- `execute flow-run` command now sends flow run log in the case of an error - [#3832](https://github.com/PrefectHQ/prefect/pull/3832)
- Changed name of logs raised by the Kubernetes Agent if they stem from infrastructure events - [#3832](https://github.com/PrefectHQ/prefect/pull/3832)
- Add `tini` to the official Prefect docker images - [#3839](https://github.com/PrefectHQ/prefect/pull/3839)
- Remove task run level heartbeats for performance - [#3842](https://github.com/PrefectHQ/prefect/pull/3842)

### Task Library

- Fix mising `job_id` in `DatabricksRunNow` task initialization - [#3793](https://github.com/PrefectHQ/prefect/issues/3793)

### Fixes

- Fix Azure result byte decoding of blob data - [#3846](https://github.com/PrefectHQ/prefect/issues/3846)
- Prefect kubernetes agent no longer relies on existence of any fields in configured Kubernetes Job Template - [#3805](https://github.com/PrefectHQ/prefect/pull/3805)
- Accept old envvar style configuration for Kubernetes agent for `--service-account-name`/`--image-pull-secrets` options - [#3814](https://github.com/PrefectHQ/prefect/pull/3814)
- Pass `as_user=False` when using `client.get_cloud_url` in `StartFlowRun` - [#3850](https://github.com/PrefectHQ/prefect/pull/3850)
- Fix AWS boto3 utility passing duplicate kwargs to client initialization - [#3857](https://github.com/PrefectHQ/prefect/pull/3857)

### Deprecations

- Storage classes have been moved from `prefect.environments.storage` to `prefect.storage`, the old import paths have been deprecated accordingly - [#3796](https://github.com/PrefectHQ/prefect/pull/3796)
- Executor classes have been moved from `prefect.engine.executors` to `prefect.executors`, the old import paths have been deprecated accordingly - [#3798](https://github.com/PrefectHQ/prefect/pull/3798)
- Deprecated use of `storage_labels` boolean kwarg on local agent - [#3800](https://github.com/PrefectHQ/prefect/pull/3800)
- Deprecated use of `--storage-labels` option from agent `start` CLI command - [#3800](https://github.com/PrefectHQ/prefect/pull/3800)
- Deprecates all `Environment` classes - users should transition to setting `flow.run_config` instead of `flow.environment` - [#3811](https://github.com/PrefectHQ/prefect/pull/3811)
- Deprecate the Fargate Agent in favor of the ECS Agent - [#3812](https://github.com/PrefectHQ/prefect/pull/3812)

### Breaking Changes

- Using in-cluster installs of the Kubernetes Agent now requires RBAC for the `events` resource - [#3783](https://github.com/PrefectHQ/prefect/pull/3783)
- Removed setting of default labels on storage objects and the local agent - [#3800](https://github.com/PrefectHQ/prefect/pull/3800)
- Remove deprecated `RemoteEnvironment`/`RemoteDaskEnvironment` - [#3802](https://github.com/PrefectHQ/prefect/pull/3802)
- Remove deprecated `executor_kwargs` argument to `KubernetesJobEnvironment`/`FargateTaskEnvironment` - [#3802](https://github.com/PrefectHQ/prefect/pull/3802)
- Remove deprecated `prefect run cloud`/`prefect run server` CLI commands - [#3803](https://github.com/PrefectHQ/prefect/pull/3803)
- Remove deprecated `prefect execute cloud-flow` CLI command - [#3803](https://github.com/PrefectHQ/prefect/pull/3803)
- Stop building the `prefecthq/prefect:all_extras` image and switch flow deployment default to using `prefecthq/prefect:{core_version}` - [#3804](https://github.com/PrefectHQ/prefect/pull/3804)
- Flows now use `RunConfig` based deployments by default - legacy `Environment` based deployments are now opt-in only - [#3806](https://github.com/PrefectHQ/prefect/pull/3806)
- Remove deprecated `prefect.contrib` module - [#3813](https://github.com/PrefectHQ/prefect/pull/3813)
- Remove all references to result handlers and safe results - [#3838](https://github.com/PrefectHQ/prefect/pull/3838)
- Remove option to enable deprecated Kubernetes resource manager in agent install CLI command - [#3840](https://github.com/PrefectHQ/prefect/pull/3840)

### Contributors

- [Christian Werner](https://github.com/cwerner)
- [Erich Oliveira](https://github.com/ericholiveira)
- [Jacob Hayes](https://github.com/JacobHayes)
- [Pedro Martins](https://github.com/pedrocwb)

## 0.13.19 <Badge text="beta" type="success" />

Released on December 8, 2020.

### Enhancements

- Use explicit exception chaining - [#3306](https://github.com/PrefectHQ/prefect/issues/3306)
- Support Bitbucket as storage option - [#3711](https://github.com/PrefectHQ/prefect/pull/3711)
- Surface pod failures and container errors in jobs deployed with the Kubernetes Agent - [3747](https://github.com/PrefectHQ/prefect/issues/3747)
- Support timeout option in GCS tasks - [#3732](https://github.com/PrefectHQ/prefect/pull/3732)
- Added storage option for AWS CodeCommit - [#3733](https://github.com/PrefectHQ/prefect/pull/3733)
- Add the image used for a flow-run to the flow run environment as `prefect.context.image` - [#3746](https://github.com/PrefectHQ/prefect/pull/3746)
- Add `UniversalRun` run-config that works with all agents - [#3750](https://github.com/PrefectHQ/prefect/pull/3750)
- Support flows that have no run-config or environment - [#3750](https://github.com/PrefectHQ/prefect/pull/3750)
- Allow Docker storage environment vars to be used in commands - [#3755](https://github.com/PrefectHQ/prefect/pull/3755)
- Add `service_account_name` and `image_pull_secrets` options to `KubernetesRun` and `KubernetesAgent` - [#3778](https://github.com/PrefectHQ/prefect/pull/3778)
- Add a new Client function `delete_project` - [#3728](https://github.com/PrefectHQ/prefect/pull/3728)

### Task Library

- Add task to fetch data from Dremio - [#3734](https://github.com/PrefectHQ/prefect/pull/3734)
- Add `RunGreatExpectationsValidation` task - [#3753](https://github.com/PrefectHQ/prefect/pull/3753)
- Add the option to post markdown artifacts from the `RunGreatExpectationsValidation` task - [#3753](https://github.com/PrefectHQ/prefect/pull/3753)

### Fixes

- Fix state attempting to read result from absent upstream result - [#3618](https://github.com/PrefectHQ/prefect/issues/3618)
- Replace deprecated download_as_string method with download_as_bytes method - [#3741](https://github.com/PrefectHQ/prefect/pull/3741)
- Fix default image whenever working on a non-tagged commit - [#3748](https://github.com/PrefectHQ/prefect/pull/3748)
- Fix type-casting for task timeout defaults loaded from config - [#3761](https://github.com/PrefectHQ/prefect/pull/3761)
- Fix the `ref` default on GitHub storage - [#3764](https://github.com/PrefectHQ/prefect/pull/3764)
- Fix rare cancellation bug when running with external Dask cluster - [#3770](https://github.com/PrefectHQ/prefect/pull/3770)

### Deprecations

- Deprecated the `RunGreatExpectationsCheckpoint` task in favor of `RunGreatExpectationsValidation` - [#3766](https://github.com/PrefectHQ/prefect/pull/3766)

### Contributors

- [BluePoof](https://github.com/BluePoof)
- [Faris ALSaleem](https://github.com/FarisALSaleem)
- [Jonathan Owen](https://github.com/jrowen)
- [Klemen Strojan](https://github.com/strojank)
- [Phillip Choi](https://github.com/philz-catz)
- [Sam Bail](https://github.com/spbail)
- [Takayuki Hirayama](https://github.com/yukihira1992)

## 0.13.18 <Badge text="beta" type="success" />

Released on November 30, 2020.

### Enhancements

- Display formatted graphql errors on client request failure - [#3632](https://github.com/PrefectHQ/prefect/pull/3632)
- Refactor Core Client API calls for performance - [#3730](https://github.com/PrefectHQ/prefect/pull/3730)

### Task Library

- Refactor execute query code for `PostgresExecute`, `PostgresExecuteMany`, and `PostgresFetch` tasks - [#3714](https://github.com/PrefectHQ/prefect/pull/3714)
- Fix `PicklingError` in `BigQueryLoadFile` and `BigQueryLoadGoogleCloudStorage` - [#3724](https://github.com/PrefectHQ/prefect/pull/3724)
- Allow custom exporter for `ExecuteNotebook` task - [#3725](https://github.com/PrefectHQ/prefect/pull/3725)
- Properly forward `location` parameter in bigquery tasks - [#3726](https://github.com/PrefectHQ/prefect/pull/3726)
- Support passing `helper_script` to `ShellTask`/`DBTShellTask` at runtime - [#3729](https://github.com/PrefectHQ/prefect/pull/3729)

### Fixes

- Fix bug with docker storage throwing exception while trying to display output - [#3717](https://github.com/PrefectHQ/prefect/pull/3717)

### Contributors

- [Amanda Wee](https://github.com/amanda-wee)
- [Panagiotis Simakis](https://github.com/sp1thas)
- [Swier Heeres](https://github.com/swierh)
- [Takayuki Hirayama](https://github.com/yukihira1992)

## 0.13.17 <Badge text="beta" type="success" />

Released on November 24, 2020.

### Features

- Improved support for Tasks returning multiple results - [#3697](https://github.com/PrefectHQ/prefect/pull/3697)

### Enhancements

- Allow chaining of `Task` imperative dependency calls - [#3696](https://github.com/PrefectHQ/prefect/pull/3696)
- Add `task_definition_arn` to `ECSRun` run-config - [#3681](https://github.com/PrefectHQ/prefect/pull/3681)
- Rerun `resource_manager` tasks when restarting flows from failed - [#3689](https://github.com/PrefectHQ/prefect/pull/3689)
- Raise nice warning if user passes `Task` instance to `Task` constructor, rather than when calling the `Task` (or using `Task.map`/`Task.set_dependencies`) - [#3691](https://github.com/PrefectHQ/prefect/pull/3691)
- Always use tenant slug in output of Client `get_cloud_url` function - [#3692](https://github.com/PrefectHQ/prefect/pull/3692)

### Task Library

- Add enhancement to `StartFlowRun` task to create link artifact for started flow run - [#3692](https://github.com/PrefectHQ/prefect/pull/3692)
- Add a new postgres task `PostgresExecuteMany` - [#3703](https://github.com/PrefectHQ/prefect/pull/3703)
- Add debug logging for Docker tasks `PullImage` and `BuildImage` - [#3672](https://github.com/PrefectHQ/prefect/pull/3672)
- `ShellTask` returns output on failure - [#3649](https://github.com/PrefectHQ/prefect/pull/3649)
- `ShellTask` allows streaming of output independently of the number of lines returned - [#3649](https://github.com/PrefectHQ/prefect/pull/3649)

### Fixes

- Make `serialized_hash` handle unordered task sets correctly - [#3682](https://github.com/PrefectHQ/prefect/pull/3682)
- Docker storage build error logs were not always displayed - [#3693](https://github.com/PrefectHQ/prefect/pull/3693)
- Fix automatic quoting of Docker storage environment variable values - [#3694](https://github.com/PrefectHQ/prefect/pull/3694)
- Use `exist_ok` flag in `os.makedirs` to avoid race condition in local storage class - [#3679](https://github.com/PrefectHQ/prefect/pull/3679)

### Contributors

- [Faris ALSaleem](https://github.com/FarisALSaleem)
- [R Max Espinoza](https://github.com/rmax)
- [Takayuki Hirayama](https://github.com/yukihira1992)

## 0.13.16 <Badge text="beta" type="success" />

Released on November 17, 2020.

### Enhancements

- Experimental support for Python 3.9 - [#3411](https://github.com/PrefectHQ/prefect/pull/3411)

### Fixes

- Fixes Flow.replace freezing reference tasks - [#3655](https://github.com/PrefectHQ/prefect/issues/3655)
- Fixed bug where `flow.serialized_hash()` could return inconsistent values across new python instances - [#3654](https://github.com/PrefectHQ/prefect/pull/3654)

### Contributors

- [Ben Fogelson](https://github.com/benfogelson)

## 0.13.15 <Badge text="beta" type="success" />

Released on November 11, 2020.

### Features

- Add API for storing task run artifacts in the backend - [#3581](https://github.com/PrefectHQ/prefect/pull/3581)

### Enhancements

- Allow for setting `Client` headers before loading tenant when running with Prefect Server - [#3515](https://github.com/PrefectHQ/prefect/issues/3515)
- Checkpoint all iterations of Looped tasks - [#3619](https://github.com/PrefectHQ/prefect/issues/3619)
- Add `ref` option to GitHub storage for specifying branches other than master - [#3638](https://github.com/PrefectHQ/prefect/issues/3638)
- Added `ExecuteNotebook` task for running Jupyter notebooks - [#3599](https://github.com/PrefectHQ/prefect/pull/3599)
- Pass `day_or` croniter argument to CronClock and CronSchedule  - [#3612](https://github.com/PrefectHQ/prefect/pull/3612)
- `Client.create_project` and `prefect create project` will skip creating the project if the project already exists - [#3630](https://github.com/PrefectHQ/prefect/pull/3630)
- Update deployments extension to AppsV1Api - [#3637](https://github.com/PrefectHQ/prefect/pull/3637)
- `PrefectSecret` and `EnvVarSecret` tasks no longer require secret names be provided at flow creation time - [#3641](https://github.com/PrefectHQ/prefect/pull/3641)

### Fixes

- Fix issue with retrying mapped pipelines on dask - [#3519](https://github.com/PrefectHQ/prefect/issues/3519)
- Task arguments take precedence when generating `task_run_name` - [#3605](https://github.com/PrefectHQ/prefect/issues/3605)
- Fix breaking change in flow registration with old server versions - [#3642](https://github.com/PrefectHQ/prefect/pull/3642)
- Task arguments take precedence when generating templated targets and locations - [#3627](https://github.com/PrefectHQ/prefect/pull/3627)

### Breaking Changes

- Environment variable config values now parse without requiring escaping backslashes - [#3603](https://github.com/PrefectHQ/prefect/issues/3603)

### Contributors

- [Amanda Wee](https://github.com/amanda-wee)
- [Avi Aminov](https://github.com/bachsh)
- [Brad McElroy](https://github.com/limx0)
- [Emilien Garreau](https://github.com/EmGarr)
- [Joël Luijmes](https://github.com/joelluijmes)
- [Panagiotis Simakis](https://github.com/sp1thas)

## 0.13.14 <Badge text="beta" type="success" />

Released on November 5, 2020.

### Features

- `flow.register` accepts an idempotency key to prevent excessive flow versions from being created - [#3590](https://github.com/PrefectHQ/prefect/pull/3590)
- Added `flow.serialized_hash()` for easy generation of hash keys from the serialized flow - [#3590](https://github.com/PrefectHQ/prefect/pull/3590)

### Enhancements

- Add option to select `cursor_type` for MySQLFetch task - [#3574](https://github.com/PrefectHQ/prefect/pull/3574)
- Add new `ECSAgent` and `ECSRun` run config - [#3585](https://github.com/PrefectHQ/prefect/pull/3585)
- Display exception information on `prefect create project` failure - [#3589](https://github.com/PrefectHQ/prefect/pull/3589)
- `prefect diagnostics` no longer displays keys that have values matching the default config - [#3593](https://github.com/PrefectHQ/prefect/pull/3593)
- Allow use of multiple image pull secrets in `KubernetesAgent`, `DaskKubernetesEnvironment` - [#3596](https://github.com/PrefectHQ/prefect/pull/3596)
- Added FROM to explicitly chain exceptions in src/prefect/tasks/twitter - [#3602](https://github.com/PrefectHQ/prefect/pull/3602)
- Add UTC offset to default logging.datefmt; logging timestamp converter now follows Python default behavior  - [#3607](https://github.com/PrefectHQ/prefect/pull/3607)
- Improve error message when API responds with 400 status code - [#3615](https://github.com/PrefectHQ/prefect/pull/3615)

### Deprecations

- Deprecate `prefect agent start <kind>` in favor of `prefect agent <kind> start` - [#3610](https://github.com/PrefectHQ/prefect/pull/3610)
- Deprecate `prefect agent install <kind>` in favor of `prefect agent <kind> install` - [#3610](https://github.com/PrefectHQ/prefect/pull/3610)

### Contributors

- [Billy McMonagle](https://github.com/speedyturkey)
- [James Lamb](https://github.com/jameslamb)
- [Juan Calderon-Perez](https://github.com/gabrielcalderon)
- [Michael Marinaccio](https://github.com/mmarinaccio)

## 0.13.13  <Badge text="beta" type="success" />

Released on October 27, 2020.

### Enhancements

- Don't stop execution if the task runner fails to load a cached result - [#3378](https://github.com/PrefectHQ/prefect/issues/3378)
- Add option to specify `networkMode` for tasks created by the Fargate Agent - [#3546](https://github.com/PrefectHQ/prefect/pull/3546)
- Allows to schedule flow runs at an arbitrary time with StartFlowRun - [#3573](https://github.com/PrefectHQ/prefect/pull/3573)

### Fixes

- Use `BlobServiceClient` instead of `BlockBlobService` to connect to azure blob in azure tasks - [#3562](https://github.com/PrefectHQ/prefect/pull/3562)
- Tasks with `log_stdout=True` work with non-utf8 output - [#3563](https://github.com/PrefectHQ/prefect/pull/3563)

### Contributors

- [Alessandro Lollo](https://github.com/AlessandroLollo)
- [Kfir Stri](https://github.com/kfirstri)
- [Lukáš Novotný](https://github.com/novotl)
- [Natalie Smith](https://github.com/thatgalnatalie)
- [Raphael Riel](https://github.com/raphael-riel)

## 0.13.12 <Badge text="beta" type="success" />

Released on October 20, 2020.

### Enhancements

- Agents now submit flow runs in order of scheduled start times - [#3165](https://github.com/PrefectHQ/prefect/issues/3165)
- Updating k8s tutorial docs to include instructions on how to provide access to S3 from kubernetes deployments on AWS - [#3200](https://github.com/PrefectHQ/prefect/issues/3200)
- Adds option to specify default values for GetItem and GetAttr tasks - [#3489](https://github.com/PrefectHQ/prefect/pull/3489)
- Allow disabling default storage labels for the `LocalAgent` - [#3503](https://github.com/PrefectHQ/prefect/pull/3503)
- Improve overall functionality of docs search, full list of changes [here](https://github.com/PrefectHQ/prefect/pull/3504#issue-503684023) - [#3504](https://github.com/PrefectHQ/prefect/pull/3504)
- Add `LocalRun` implementation for `run_config` based flows - [#3527](https://github.com/PrefectHQ/prefect/pull/3527)
- Add `DockerRun` implementation for `run_config` based flows - [#3537](https://github.com/PrefectHQ/prefect/pull/3537)
- Raise a better error message when trying to register a flow with a schedule using custom filter functions - [#3450](https://github.com/PrefectHQ/prefect/pull/3540)
- `RenameFlowRunTask`: use default `flow_run_id` value from context - [#3548](https://github.com/PrefectHQ/prefect/pull/3548)
- Raise a better error message when trying to register a flow with parameters with JSON-incompatible defaults - [#3549](https://github.com/PrefectHQ/prefect/pull/3549)

### Task Library

- Extended `GCSUpload` task to allow uploading of bytes/gzip data - [#3507](https://github.com/PrefectHQ/prefect/issues/3507)
- Allow setting runtime `webook_secret` on `SlackTask` and kwarg for `webhook_secret` retrieved from `PrefectSecret` task - [#3522](https://github.com/PrefectHQ/prefect/pull/3522)

### Fixes

- Fix `get flow-runs` and `describe flow-runs` CLI commands querying of removed `duration` field - [#3517](https://github.com/PrefectHQ/prefect/issues/3517)
- Fix multiprocess based timeout handler on linux - [#3526](https://github.com/PrefectHQ/prefect/pull/3526)
- Fix API doc generation incorrectly compiling mocked imports - [#3504](https://github.com/PrefectHQ/prefect/pull/3504)
- Fix multiprocessing scheduler failure while running tasks with timeouts - [#3511](https://github.com/PrefectHQ/prefect/pull/3511)
- Update Fargate task definition validation - [#3514](https://github.com/PrefectHQ/prefect/pull/3514)
- Fix bug in k8s where the resource-manager would sometimes silently crash on errors - [#3521](https://github.com/PrefectHQ/prefect/pull/3521)
- Add labels from `flow.storage` for `run_config` based flows - [#3527](https://github.com/PrefectHQ/prefect/pull/3527)
- Fix LocalAgent PYTHONPATH construction on Windows - [#3551](https://github.com/PrefectHQ/prefect/pull/3551)

### Deprecations

- `FlowRunTask`, `RenameFlowRunTask`, and `CancelFlowRunTask` have been renamed to `StartFlowRun`, `RenameFlowRun`, and `CancelFlowRun` respectively - [#3539](https://github.com/PrefectHQ/prefect/pull/3539)

### Contributors

- [Michal Baumgartner](https://github.com/m1so)
- [Panagiotis Simakis](https://github.com/sp1thas)
- [Raphael Riel](https://github.com/raphael-riel)
- [Spencer Ellinor](https://github.com/zpencerq)
- [andywaugh](https://github.com/andywaugh)

## 0.13.11 <Badge text="beta" type="success" />

Released on October 14, 2020.

### Features

- Allow for schedules that emit custom Flow Run labels - [#3483](https://github.com/PrefectHQ/prefect/pull/3483)

### Enhancements

- Use explicit exception chaining - [#3306](https://github.com/PrefectHQ/prefect/issues/3306)
- S3List filtering using the LastModified value - [#3460](https://github.com/PrefectHQ/prefect/pull/3460)
- Add Gitlab storage - [#3461](https://github.com/PrefectHQ/prefect/pull/3461)
- Extend module storage capabilities - [#3463](https://github.com/PrefectHQ/prefect/pull/3463)
- Support adding additional flow labels in `prefect register flow` - [#3465](https://github.com/PrefectHQ/prefect/pull/3465)
- Strict Type for default value of a Parameter - [#3466](https://github.com/PrefectHQ/prefect/pull/3466)
- Enable automatic script upload for file-based storage when using S3 and GCS - [#3482](https://github.com/PrefectHQ/prefect/pull/3482)
- Allow for passing labels to `client.create_flow_run` - [#3483](https://github.com/PrefectHQ/prefect/pull/3483)
- Display flow group ID in registration output URL instead of flow ID to avoid redirect in UI - [#3500](https://github.com/PrefectHQ/prefect/pull/3500)
- Add informative error log when local storage fails to load flow - [#3475](https://github.com/PrefectHQ/prefect/pull/3475)

### Task Library

- Add cancel flow run task - [#3484](https://github.com/PrefectHQ/prefect/issues/3484)
- Add new `BatchSubmit` task for submitting jobs to AWS batch - [#3366](https://github.com/PrefectHQ/prefect/pull/3366)
- Add new `AWSClientWait` task for waiting on long-running AWS jobs - [#3366](https://github.com/PrefectHQ/prefect/pull/3366)
- Add GetAttr task - [#3481](https://github.com/PrefectHQ/prefect/pull/3481)

### Fixes

- Fix default profile directory creation behavior - [#3037](https://github.com/PrefectHQ/prefect/issues/3037)
- Fix `DaskKubernetesEnvironment` overwriting log attributes for custom specs - [#3231](https://github.com/PrefectHQ/prefect/issues/3231)
- Fix default behavior for `dbt_kwargs` in the dbt task to provide an empty string - [#3280](https://github.com/PrefectHQ/prefect/issues/3280)
- Fix containerDefinitions environment validation - [#3452](https://github.com/PrefectHQ/prefect/pull/3452)
- Raise a better error when calling `flow.register()` from within a `Flow` context - [#3467](https://github.com/PrefectHQ/prefect/pull/3467)
- Fix task cancellation on Python 3.8 to properly interrupt long blocking calls - [#3474](https://github.com/PrefectHQ/prefect/pull/3474)

### Contributors

- [Aaron Richter](https://github.com/rikturr)
- [Alessandro Lollo](https://github.com/https://github.com/AlessandroLollo)
- [Bruno Casarotti](https://github.com/brunocasarotti)
- [Mariia Kerimova](https://github.com/mashun4ek)
- [Max Del Giudice](https://github.com/madelgi)
- [Michal Baumgartner](https://github.com/m1so)
- [Panagiotis Simakis](https://github.com/sp1thas)
- [Raphael Riel](https://github.com/raphael-riel)
- [Shalika Singhal](https://github.com/shalika10)
- [Zach McQuiston](https://github.com/zmac12)
- [heyitskevin](https://github.com/heyitskevin)

## 0.13.10 <Badge text="beta" type="success" />

Released on October 6, 2020.

### Enhancements

- Add option to template task run name at runtime when using backend API - [#2100](https://github.com/PrefectHQ/prefect/issues/2100)
- Add `set_task_run_name` Client function - [#2100](https://github.com/PrefectHQ/prefect/issues/2100)
- Use 'from' to explicitly chain exceptions - [#3306](https://github.com/PrefectHQ/prefect/pull/3306)
- Update error message when registering flow to non-existant project - [#3418](https://github.com/PrefectHQ/prefect/pull/3418)
- Add `flow.run_config`, an *experimental* design for configuring deployed flows - [#3333](https://github.com/PrefectHQ/prefect/pull/3333)
- Allow python path in Local storage - [#3351](https://github.com/PrefectHQ/prefect/pull/3351)
- Enable agent registration for server users - [#3385](https://github.com/PrefectHQ/prefect/pull/3385)
- Added FROM to explicitly chain exceptions in src/prefect/utilities - [#3429](https://github.com/PrefectHQ/prefect/pull/3429)

### Task Library

- Add keypair auth for snowflake - [#3404](https://github.com/PrefectHQ/prefect/pull/3404)
- Add new `RenameFlowRunTask` for renaming a currently running flow - [#3285](https://github.com/PrefectHQ/prefect/issues/3285).

### Fixes

- Fix mypy typing for `target` kwarg on base Task class - [#2100](https://github.com/PrefectHQ/prefect/issues/2100)
- Fix Fargate Agent not parsing cpu and memory provided as integers - [#3423](https://github.com/PrefectHQ/prefect/pull/3423)
- Fix MySQL Tasks breaking on opening a context - [#3426](https://github.com/PrefectHQ/prefect/pull/3426)

### Contributors

- [Ian Fridge](https://github.com/fridgei)
- [Jack D. Sundberg](https://github.com/jacksund)
- [Juan Calderon-Perez](https://github.com/gabrielcalderon)
- [Max Del Giudice](https://github.com/madelgi)
- [Paras Luthra](https://github.com/luthrap)
- [Tenzin Choedak](https://github.com/tchoedak)

## 0.13.9 <Badge text="beta" type="success" />

Released on September 29, 2020.

### Features

- Allow for scheduling the same flow at the same time with multiple parameter values - [#2510](https://github.com/PrefectHQ/prefect/issues/2510)

### Enhancements

- Adopt explicit exception chaining in more places - [#3306](https://github.com/PrefectHQ/prefect/issues/3306)
- Add `DateTimeParameter` - [#3327](https://github.com/PrefectHQ/prefect/pull/3327)

### Task Library

- New task for the task library to create an item in Monday - [#3387](https://github.com/PrefectHQ/prefect/pull/3387)
- Add option to specify `run_name` for `FlowRunTask` - [#3393](https://github.com/PrefectHQ/prefect/pull/3393)

### Contributors

- [Nejc Vesel](https://github.com/veseln)
- [Sumit Datta](https://github.com/brainless)

## 0.13.8 <Badge text="beta" type="success" />

Released on September 22, 2020.

### Enhancements

- Allow passing context values as JSON string from CLI - [#3347](https://github.com/PrefectHQ/prefect/issues/3347)
- Allow copying of directories into Docker image - [#3299](https://github.com/PrefectHQ/prefect/pull/3299)
- Adds schedule filters for month end or month start and specific day - [#3330](https://github.com/PrefectHQ/prefect/pull/3330)
- Support configuring executor on flow, not on environment - [#3338](https://github.com/PrefectHQ/prefect/pull/3338)
- Support configuring additional docker build commands on `Docker` storage - [#3342](https://github.com/PrefectHQ/prefect/pull/3342)
- Support submission retries within the k8s agent - [#3344](https://github.com/PrefectHQ/prefect/pull/3344)
- Expose `flow_run_name` to `flow.run()` for local runs - [#3364](https://github.com/PrefectHQ/prefect/pull/3364)

### Task Library

- Add contributing documentation for task library - [#3360](https://github.com/PrefectHQ/prefect/pull/3360)
- Remove duplicate task library documentation in favor of API reference docs - [#3360](https://github.com/PrefectHQ/prefect/pull/3360)

### Fixes

- Fix issue with constants when copying Flows - [#3319](https://github.com/PrefectHQ/prefect/issues/3319)
- Fix `DockerAgent` with `--show-flow-logs` to work on windows/osx (with python >= 3.8) - [#3339](https://github.com/PrefectHQ/prefect/pull/3339)
- Fix mypy type checking for tasks created with `prefect.task` - [#3346](https://github.com/PrefectHQ/prefect/pull/3346)
- Fix bug in `flow.visualize()` where no output would be generated when running with `PYTHONOPTIMIZE=1` - [#3352](https://github.com/PrefectHQ/prefect/pull/3352)
- Fix typo in `DaskCloudProviderEnvironment` logs - [#3354](https://github.com/PrefectHQ/prefect/pull/3354)

### Deprecations

- Deprecate the use of the `/contrib` directory - [#3360](https://github.com/PrefectHQ/prefect/pull/3360)
- Deprecate importing `Databricks` and `MySQL` tasks from `prefect.contrib.tasks`, should use `prefect.tasks` instead - [#3360](https://github.com/PrefectHQ/prefect/pull/3360)

### Contributors

- [David Severin Ryberg](https://github.com/sevberg)
- [James Lamb](https://github.com/jameslamb)
- [Nejc Vesel](https://github.com/veseln)

## 0.13.7 <Badge text="beta" type="success" />

Released on September 16, 2020.

### Enhancements

- Use explicit exception chaining [#3306](https://github.com/PrefectHQ/prefect/issues/3306)
- Quiet Hasura logs with `prefect server start` - [#3296](https://github.com/PrefectHQ/prefect/pull/3296)

### Fixes

- Fix issue with result configuration not being respected by autogenerated tasks - [#2989](https://github.com/PrefectHQ/prefect/issues/2989)
- Fix issue with result templating that failed on task arguments named 'value' - [#3034](https://github.com/PrefectHQ/prefect/issues/3034)
- Fix issue restarting Mapped pipelines with no result- [#3246](https://github.com/PrefectHQ/prefect/issues/3246)
- Fix handling of Prefect Signals when Task state handlers are called - [#3258](https://github.com/PrefectHQ/prefect/issues/3258)
- Allow using `apply_map` under a `case` or `resource_manager` block - [#3293](https://github.com/PrefectHQ/prefect/pull/3293)
- Fix bug with interaction between `case` blocks and `Constant` tasks which resulted in some tasks never skipping - [#3293](https://github.com/PrefectHQ/prefect/pull/3293)
- Fix bug in `DaskExecutor` where not all client timeouts could be configured via setting `distributed.comm.timeouts.connect` - [#3317](https://github.com/PrefectHQ/prefect/pull/3317)

## Task Library

- Adds a compression argument to both S3Upload and S3Download, allowing for compression of data upon upload and decompression of data upon download - [#3259](https://github.com/PrefectHQ/prefect/issues/3259)

### Contributors

- [Eric Lundy](https://github.com/ericlundy87/)
- [James Lamb](https://github.com/jameslamb)
- [Max Del Giudice](https://github.com/madelgi)

## 0.13.6 <Badge text="beta" type="success" />

Released on September 9, 2020.

### Enhancements

- Adds logger to global context to remove friction on running task unit tests - [#3256](https://github.com/PrefectHQ/prefect/issues/3256)
- Expand FunctionTask AttributeError Message - [#3248](https://github.com/PrefectHQ/prefect/pull/3248)
- Add backend info to diagnostics - [#3265](https://github.com/PrefectHQ/prefect/pull/3265)
- Ellipsis Support for GraphQL DSL - [#3268](https://github.com/PrefectHQ/prefect/pull/3268)

### Task Library

- Add `DatabricksRunNow` task for running Spark jobs on Databricks - [#3247](https://github.com/PrefectHQ/prefect/pull/3247)
- Add GitHub `CreateIssueComment` task - [#3269](https://github.com/PrefectHQ/prefect/pull/3269)
- Add `S3List` task for listing keys in an S3 bucket - [#3282](https://github.com/PrefectHQ/prefect/pull/3282)
- Add `boto_kwargs` to AWS tasks - [#3275](https://github.com/PrefectHQ/prefect/pull/3275)

### Fixes

- Make identifier optional in `KubernetesAgent.replace_job_spec_yaml()` - [#3251](https://github.com/PrefectHQ/prefect/pull/3251)
- Change `https://localhost` to `http://localhost` in the welcome message - [#3271](https://github.com/PrefectHQ/prefect/pull/3271)

### Contributors

- [Ashmeet Lamba](https://github.com/ashmeet13)
- [Ashton Sidhu](https://github.com/Ashton-Sidhu)
- [Bas Nijholt](https://github.com/basnijholt)
- [Harutaka Kawamura](https://github.com/harupy)
- [James Lamb](https://github.com/jameslamb)
- [Max Del Giudice](https://github.com/madelgi)
- [Robin Beer](https://github.com/Zaubeerer)
- [Rowan Molony](https://github.com/rdmolony)
- [Shunwen](https://github.com/shunwen)

## 0.13.5 <Badge text="beta" type="success" />

Released on September 1, 2020.

### Enhancements

- Begin storing the width of mapped pipelines on the parent Mapped state - [#3233](https://github.com/PrefectHQ/prefect/issues/3233)
- Kubernetes agent now manages lifecycle of prefect jobs in its namespace - [#3158](https://github.com/PrefectHQ/prefect/pull/3158)
- Move agent heartbeat to background thread - [#3158](https://github.com/PrefectHQ/prefect/pull/3158)
- Handles `ModuleNotFound` errors in the storage healthcheck - [#3225](https://github.com/PrefectHQ/prefect/pull/3225)
- Raises the `warnings.warn` stack level to 2 to reduce duplicate warning messages - [#3225](https://github.com/PrefectHQ/prefect/pull/3225)
- Add some extra output to the `client.register` print output for visibility - [#3225](https://github.com/PrefectHQ/prefect/pull/3225)
- CLI help text docstrings are now auto documented using the API documentation parser - [#3225](https://github.com/PrefectHQ/prefect/pull/3225)
- `DaskExecutor` now logs dask worker add/removal events - [#3227](https://github.com/PrefectHQ/prefect/pull/3227)

### Fixes

- Fix issue with passing --env-vars flag to K8s Agent Install manifest - [#3239](https://github.com/PrefectHQ/prefect/issues/3239)
- Fix edge case with `add_edge` method - [#3230](https://github.com/PrefectHQ/prefect/pull/3230)

### Deprecations

- Kubernetes resource manager is now deprecated and the functionality is moved into the Kubernetes agent - [#3158](https://github.com/PrefectHQ/prefect/pull/3158)

### Contributors

- [shaunc](https://github.com/shaunc)

## 0.13.4 <Badge text="beta" type="success" />

Released on August 25, 2020.

### Enhancements

- Allow for setting path to a custom job YAML spec on the Kubernetes Agent - [#3046](https://github.com/PrefectHQ/prefect/pull/3046)
- Use better coupled versioning scheme for Core / Server / UI images - [#3204](https://github.com/PrefectHQ/prefect/pull/3204)
- Added option to mount volumes with KubernetesAgent  - [#1234](https://github.com/PrefectHQ/prefect/pull/3210)
- Add more kwargs to State.children and State.parents for common access patterns - [#3212](https://github.com/PrefectHQ/prefect/pull/3212)
- Reduce size of `prefecthq/prefect` Docker image - [#3215](https://github.com/PrefectHQ/prefect/pull/3215)

### Task Library

- Add `DatabricksSubmitRun` task for submitting Spark jobs on Databricks - [#3166](https://github.com/PrefectHQ/prefect/pull/3166)

### Fixes

- Fix Apollo service error output while waiting for GraphQL service with `prefect server start` - [#3150](https://github.com/PrefectHQ/prefect/pull/3150)
- Fix `--api` CLI option not being respected by agent Client  - [#3186](https://github.com/PrefectHQ/prefect/pull/3186)
- Fix state message when using targets - [#3216](https://github.com/PrefectHQ/prefect/pull/3216)

### Contributors

- [Ashton Sidhu](https://github.com/Ashton-Sidhu)
- [Chris Martin](https://github.com/d80tb7)
- [Juan Calderon-Perez](https://github.com/gabrielcalderon)
- [Thomas Frederik Hoeck](https://github.com/thomasfrederikhoeck)
- [VincentTNR](https://github.com/VincentTNR)
- [emcake](https://github.com/emcake)

## 0.13.3 <Badge text="beta" type="success" />

Released on August 18, 2020.

### Enhancements

- Make use of `kubernetes` extra logger in the `DaskKubernetesEnvironment` optional - [#2988](https://github.com/PrefectHQ/prefect/issues/2988)
- Make Client robust to simplejson - [#3151](https://github.com/PrefectHQ/prefect/issues/3151)
- Raise Warning instead of Exception during storage healthcheck when Result type is not provided - [#3146](https://github.com/PrefectHQ/prefect/pull/3146)
- Add `server create-tenant` for creating a tenant on the server - [#3147](https://github.com/PrefectHQ/prefect/pull/3147)
- Cloud logger now responds to logging level - [#3179](https://github.com/PrefectHQ/prefect/pull/3179)

### Task Library

- Add support for [`host_config`](https://docker-py.readthedocs.io/en/stable/api.html#docker.api.container.ContainerApiMixin.create_host_config) and arbitrary keyword arguments in `Docker` tasks - [#3173](https://github.com/PrefectHQ/prefect/pull/3173)

### Fixes

- Fix empty string `imagePullSecrets` issue on AKS by removing if not set - [#3142](https://github.com/PrefectHQ/prefect/issues/3142)
- Fix querying for cached states with no `cache_key` - [#3168](https://github.com/PrefectHQ/prefect/pull/3168)
- Fix access to `core_version` in Agent's `get_flow_run_command()` - [#3177](https://github.com/PrefectHQ/prefect/pull/3177)

### Breaking Changes

- DaskKubernetesEnvironment no longer logs Kubernetes errors by default - [#2988](https://github.com/PrefectHQ/prefect/issues/2988)
- Logging level in Cloud now defaults to INFO - [#3179](https://github.com/PrefectHQ/prefect/pull/3179)

### Contributors

- [James Lamb](https://github.com/jameslamb)
- [Nelson Cornet](https://github.com/sk4la)
- [Zach Angell](https://github.com/zangell44)

## 0.13.2 <Badge text="beta" type="success" />

Released on August 11, 2020.

### Features

- Pandas DataFrame Serializer - [#3020](https://github.com/PrefectHQ/prefect/pull/3020), [#2963](https://github.com/PrefectHQ/prefect/pull/2963), [#2917](https://github.com/PrefectHQ/prefect/issues/2917)

### Enhancements

- Agents set flow run execution command based on flow's core version - [#3113](https://github.com/PrefectHQ/prefect/pull/3113)
- Clean up extra labels on jobs created by Kubernetes agent - [#3129](https://github.com/PrefectHQ/prefect/pull/3129)

### Task Library

- Return `LoadJob` object in `BigQueryLoad` tasks - [#3086](https://github.com/PrefectHQ/prefect/issues/3086)

### Fixes

- Fix bug with `LocalDaskExecutor('processes')` that allowed tasks to be run multiple times in certain cases - [#3127](https://github.com/PrefectHQ/prefect/pull/3127)
- Add toggle to bypass bug in `slack_notifier` that attempted to connect to backend even if the backend didn't exist - [#3136](https://github.com/PrefectHQ/prefect/pull/3136)

### Contributors

- [Andrew Schechtman-Rook](https://github.com/AndrewRook)
- [Franklin Winokur](https://github.com/fwinokur)
- [Fraznist](https://github.com/Fraznist)
- [Jackson Maxfield Brown](https://github.com/JacksonMaxfield)

## 0.13.1 <Badge text="beta" type="success" />

Released on August 6, 2020.

### Fixes

- Fix issue with 0.13.0 agents not able to run Flows registered with older Core versions - [#3111](https://github.com/PrefectHQ/prefect/pull/3111)


## 0.13.0 <Badge text="beta" type="success" />

Released on August 6, 2020.

### Features

- Support cancellation of active flow runs - [#2942](https://github.com/PrefectHQ/prefect/pull/2942)
- Add Webhook storage - [#3000](https://github.com/PrefectHQ/prefect/pull/3000)

### Enhancements

- Only supply versions when setting `SUBMITTED` and `RUNNING` states - [#2730](https://github.com/PrefectHQ/prefect/issues/2730)
- Gracefully recover from version lock errors - [#2731](https://github.com/PrefectHQ/prefect/issues/2731)
- Add `--ui-version` server start CLI option to run a specific UI image - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)
- Agent querying of flow runs now passes active tenant ID - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)
- Ignore calls to flow.register when parsing a flow using file based storage - [#3051](https://github.com/PrefectHQ/prefect/issues/3051)

### Task Library

- Allow idempotency keys in `FlowRunTask` when using server backend - [#3006](https://github.com/PrefectHQ/prefect/issues/3006)
- Require project name in `FlowRunTask` when using server backend - [#3006](https://github.com/PrefectHQ/prefect/issues/3006)

### Fixes

- Fix use of absolute path in Docker storage on Windows - [#3044](https://github.com/PrefectHQ/prefect/pull/3044)
- Determine if checkpointing is enabled from config set in the flow-runner process - [#3085](https://github.com/PrefectHQ/prefect/pull/3085)
- Fix `--no-ui` server start CLI option still attempting to pull UI image - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)

### Deprecations

- Deprecate `execute cloud-flow` CLI command in favor of `execute flow-run` - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)
- Deprecate `run server/cloud` CLI commands in favor of `run flow` - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)

### Breaking Changes

- Move server and UI code out into separate repositories - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)
- Project names are now required when managing flows with the core server - [#3087](https://github.com/PrefectHQ/prefect/pull/3087)

### Contributors

- [James Lamb](https://github.com/jameslamb)
- [Pravin Dahal](https://github.com/pravindahal)
- [Panagiotis Simakis](https://github.com/sp1thas)

## 0.12.6 <Badge text="beta" type="success" />

Released on July 28, 2020.

### Features

- Add `flatten` operator for unnesting and flat-maps - [#2898](https://github.com/PrefectHQ/prefect/pull/2898)

### Enhancements

- Add retry_on_api_error flag to client methods - [#3012](https://github.com/PrefectHQ/prefect/pull/3012)
- Add `reg_allow_list` option for Docker Agent - [#3026](https://github.com/PrefectHQ/prefect/pull/3026#issuecomment-663078217)
- Update FargateTaskEnvironment to throw if task definition is inconsistent with existing task definition - [#3031](https://github.com/PrefectHQ/prefect/pull/3031)

### Fixes

- Cleanup to ShellTask to close open stdout file which was observable in some cases - [#3002](https://github.com/PrefectHQ/prefect/issues/3002)
- Fix check of flow existence in storage object `get_flow` to only occur when provided - [#3027](https://github.com/PrefectHQ/prefect/issues/3027)
- Use fullname and tag when Docker Storage determines if build was successful - [#3029](https://github.com/PrefectHQ/prefect/pull/3029)
- Prevent duplicated agent labels - [#3029](https://github.com/PrefectHQ/prefect/pull/3042)

### Deprecations

- `prefect.utilities.tasks.unmapped` moved to `prefect.utilities.edges.unmapped` - [#2898](https://github.com/PrefectHQ/prefect/pull/2898)

### Breaking Changes

- Remove `dbt` extra from dependencies - [#3018](https://github.com/PrefectHQ/prefect/pull/3018)

### Contributors

- [James Lamb](https://github.com/jameslamb)
- [Spencer Ellinor](https://github.com/zpencerq)
- [Thomas Frederik Hoeck](https://github.com/thomasfrederikhoeck)
- [berosen](https://github.com/berosen)

## version=0.12.5 <Badge text="beta" type="success" />

Released on July 21, 2020.

### Features

- Add `resource_manager` api for cleaner setup/cleanup of temporary resources - [#2913](https://github.com/PrefectHQ/prefect/pull/2913)

### Enhancements

- Add `new_flow_context` to FlowRunTask for configurable context - [#2941](https://github.com/PrefectHQ/prefect/issues/2941)
- All storage types now support file-based storage - [#2944](https://github.com/PrefectHQ/prefect/pull/2944)
- Turn work stealing ON by default on Dask K8s environment - [#2973](https://github.com/PrefectHQ/prefect/pull/2973)
- Send regular heartbeats while waiting to retry / dequeue - [#2977](https://github.com/PrefectHQ/prefect/pull/2977)
- Cached states now validate based on `hashed_inputs` for more efficient storage - [#2984](https://github.com/PrefectHQ/prefect/pull/2984)
- Simplify creation of optional parameters with default of `None` - [#2995](https://github.com/PrefectHQ/prefect/pull/2995)

### Task Library

- Implement AWSSecretsManager task - [#2069](https://github.com/PrefectHQ/prefect/issues/2069)
- Update return value and config for DbtShellTask - [#2980](https://github.com/PrefectHQ/prefect/pull/2980)

### Fixes

- Don't send idempotency key when running against a local backend - [#3001](https://github.com/PrefectHQ/prefect/issues/3001)
- Fix bug in `DaskExecutor` when running with external cluster where dask clients could potentially be leaked - [#3009](https://github.com/PrefectHQ/prefect/pull/3009)

### Deprecations

- All states have deprecated the usage of `cached_inputs` - [#2984](https://github.com/PrefectHQ/prefect/pull/2984)

### Breaking Changes

- Remove password from Postgres tasks' initialization methods for security - [#1345](https://github.com/PrefectHQ/prefect/issues/1345)

### Contributors

- [Robin Beer](https://github.com/Zaubeerer)

## 0.12.4 <Badge text="beta" type="success" />

Released on July 14, 2020.

### Enhancements

- Improve output formatting of `prefect describe` CLI - [#2934](https://github.com/PrefectHQ/prefect/pull/2934)
- Add new `wait` kwarg to Flow Run Task for reflecting the flow run state in the task - [#2935](https://github.com/PrefectHQ/prefect/pull/2935)
- Separate build-time and run-time job spec details in KubernetsJobEnvironment - [#2950](https://github.com/PrefectHQ/prefect/pull/2950)

### Task Library

- Implement RunNamespacedJob task for Kubernetes - [#2916](https://github.com/PrefectHQ/prefect/pull/2916)
- Add `log_stderr` option to `ShellTask` and `DbtShellTask` for logging the full output from stderr - [#2961](https://github.com/PrefectHQ/prefect/pull/2961)

### Fixes

- Ensure `is_serializable` always uses same executable for subprocess. - [#1262](https://github.com/PrefectHQ/prefect/issues/1262)
- Fix issue with Mapped tasks not always reloading child state results on reruns - [#2656](https://github.com/PrefectHQ/prefect/issues/2656)
- Fix `FargateTaskEnvironment` attempting to retrieve authorization token when not present - [#2940](https://github.com/PrefectHQ/prefect/pull/2940)
- Fix issue with Metastates compounding - [#2965](https://github.com/PrefectHQ/prefect/pull/2965)

### Contributors

- [Chris Bowdon](https://github.com/cbowdon)
- [James Lamb](https://github.com/jameslamb)
- [Paweł Cieśliński](https://github.com/pcieslinski)

## 0.12.3 <Badge text="beta" type="success" />

Released on July 8, 2020.

### Enhancements

- Update `flow.slugs` during `flow.replace` - [#2919](https://github.com/PrefectHQ/prefect/issues/2919)
- `flow.update` accepts the optional kwarg `merge_parameters` that allows flows to be updated with common `Parameters` - [#2501](https://github.com/PrefectHQ/prefect/issues/2501)
- Added poke handler to notify agent process of available flow runs - [#2914](https://github.com/PrefectHQ/prefect/pull/2914)
- Add `Cancelling` state for indicating a flow-run that is being cancelled, but may still have tasks running - [#2923](https://github.com/PrefectHQ/prefect/pull/2923)

### Task Library

- Add `ReadAirtableRow` task - [#2843](https://github.com/PrefectHQ/prefect/pull/2843)
- Add `container_name` kwarg to `CreateContainer` Docker task - [#2904](https://github.com/PrefectHQ/prefect/pull/2904)
- Adds an `extra_docker_kwargs` argument to `CreateContainer` Docker task - [#2915](https://github.com/PrefectHQ/prefect/pull/2915)

### Fixes

- Fix issue with short-interval IntervalClocks that had a start_date far in the past - [#2906](https://github.com/PrefectHQ/prefect/pull/2906)
- When terminating early, executors ensure all pending work is cancelled/completed before returning, ensuring no lingering background processing - [#2920](https://github.com/PrefectHQ/prefect/pull/2920)

### Contributors

- [Bradley McElroy](https://github.com/limx0)
- [Itay Livni](https://github.com/gryBox)
- [Matthew Alhonte](https://github.com/mattalhonte)
- [Panagiotis Simakis](https://github.com/sp1thas)
- [Sandeep Aggarwal](https://github.com/asandeep)

## 0.12.2 <Badge text="beta" type="success" />

Released on June 30, 2020.

### Features

- Add `apply_map`, a function to simplify creating complex mapped pipelines - [#2846](https://github.com/PrefectHQ/prefect/pull/2846)

### Enhancements

- Make storage location inside Docker storage configurable - [#2865](https://github.com/PrefectHQ/prefect/pull/2865)
- Send heartbeats on each iteration of the Cloud task runner's retry loop - [#2893](https://github.com/PrefectHQ/prefect/pull/2893)

### Task Library

- Add option to BigQueryTask to return query as dataframe - [#2862](https://github.com/PrefectHQ/prefect/pull/2862)

### Server

- None

### Fixes

- Add more context keys when running locally so that templating is consistent between local and Cloud runs - [#2662](https://github.com/PrefectHQ/prefect/issues/2662)
- Fix Fargate agent not parsing string provided containerDefinitions - [#2875](https://github.com/PrefectHQ/prefect/issues/2875)
- Fix Fargate agent providing empty parameters if not set - [#2878](https://github.com/PrefectHQ/prefect/issues/2878)
- Fix issue with Queued task runs flooding agents with work - [#2884](https://github.com/PrefectHQ/prefect/issues/2884)
- Add missing `prefect register flow` to CLI help text - [#2895](https://github.com/PrefectHQ/prefect/pull/2895)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [James Lamb](https://github.com/jameslamb)
- [nathaniel-md](https://github.com/nathaniel-md)

## 0.12.1 <Badge text="beta" type="success" />

Released on June 25, 2020.

### Features

- Task slugs are now stable across rebuilds of the same Flow - [#2531](https://github.com/PrefectHQ/prefect/pull/2531)
- Support configuring executors for `LocalEnvironment`, `KubernetesJobEnvironment`, and `FargateTaskEnvironment` - [#2805](https://github.com/PrefectHQ/prefect/pull/2805)
- Flows can now be stored and executed using file-based storage - [#2840](https://github.com/PrefectHQ/prefect/pull/2840)

### Enhancements

- Add option to set `repositoryCredentials` on Fargate Agent `containerDefinitions` - [#2822](https://github.com/PrefectHQ/prefect/issues/2822)
- Update GraphQL endpoint to `/graphql` - [#2669](https://github.com/PrefectHQ/prefect/pull/2669)
- Allow Cloud Flow Runners to interact properly with Queued runs - [#2741](https://github.com/PrefectHQ/prefect/pull/2741)
- Add `Result` serializers - [#2755](https://github.com/PrefectHQ/prefect/pull/2755)
- Simplify `DaskExecutor` internals - [#2817](https://github.com/PrefectHQ/prefect/pull/2817)
- Set task names in `LocalDaskExecutor` - [#2819](https://github.com/PrefectHQ/prefect/pull/2819)
- Flows registered without an image set will default to `all_extras` - [#2828](https://github.com/PrefectHQ/prefect/pull/2828)
- Improve error message when sending unauthorized requests to Cloud - [#2810](https://github.com/PrefectHQ/prefect/issues/2810)
- Forward state change status back to core - [#2839](https://github.com/PrefectHQ/prefect/pull/2839)
- Add GitHub storage for storing flows as files in a GitHub repo - [#2840](https://github.com/PrefectHQ/prefect/pull/2840)
- Add `prefect register flow` CLI command for registering flows from files - [#2840](https://github.com/PrefectHQ/prefect/pull/2840)
- Add default `GITHUB_ACCESS_TOKEN` secret - [#2840](https://github.com/PrefectHQ/prefect/pull/2840)
- Create utility function for getting Kubernetes client - [#2845](https://github.com/PrefectHQ/prefect/pull/2845)

### Task Library

- Adds a MySQL task using pymysql driver - [#2124](https://github.com/PrefectHQ/prefect/issues/2124)
- Add some tasks for working with Google Sheets - [#2614](https://github.com/PrefectHQ/prefect/pull/2614)
- Add support for HTML content in the EmailTask - [#2811](https://github.com/PrefectHQ/prefect/pull/2811)

### Server

- Failing to set a state raises errors more aggressively - [#2708](https://github.com/PrefectHQ/prefect/pull/2708)

### Fixes

- Fix `all_extras` tag not being set during CI job to build image - [#2801](https://github.com/PrefectHQ/prefect/issues/2801)
- Quiet *no candidate Cached states were valid* debug logging - [#2815](https://github.com/PrefectHQ/prefect/issues/2815)
- Fix `LocalEnvironment` execute function's use of the flow object - [#2804](https://github.com/PrefectHQ/prefect/pull/2804)
- Properly set task names when using `DaskExecutor` - [#2814](https://github.com/PrefectHQ/prefect/issues/2814)
- Fix the `LocalDaskExecutor` to only compute tasks once, not multiple times - [#2819](https://github.com/PrefectHQ/prefect/pull/2819)
- Generate key names for mapped tasks that work better with Dask's dashboard - [#2831](https://github.com/PrefectHQ/prefect/pull/2831)
- Fix FlowRunTask when running against locally deployed Server - [#2832](https://github.com/PrefectHQ/prefect/pull/2832)
- Make sure image from Docker storage is always used with KubernetesJobEnvironment - [#2838](https://github.com/PrefectHQ/prefect/pull/2838)
- Change Environment.run_flow() to prefer executor from flow's environment - [#2849](https://github.com/PrefectHQ/prefect/pull/2849)

### Deprecations

- Deprecate `RemoteEnvironment` in favor of `LocalEnvironment` - [#2805](https://github.com/PrefectHQ/prefect/pull/2805)
- Deprecate `RemoteDaskEnvironment` in favor of `LocalEnvironment` with a `DaskExecutor` - [#2805](https://github.com/PrefectHQ/prefect/pull/2805)
- Deprecate `executor_kwargs` in `KubernetesJobEnvironment` and `FargateTaskEnvironment` in favor of `executor` - [#2805](https://github.com/PrefectHQ/prefect/pull/2805)

### Breaking Changes

- Remove previously deprecated `SynchronousExecutor` - [#2826](https://github.com/PrefectHQ/prefect/pull/2826)

### Contributors

- [manesioz](https://github.com/manesioz)
- [Alex Cano](https://github.com/alexisprince1994)
- [James Lamb](https://github.com/jameslamb)
- [Matthew Alhonte](https://github.com/mattalhonte/)
- [Paweł Cieśliński](https://github.com/pcieslinski)

## 0.12.0 <Badge text="beta" type="success" />

Released on June 17, 2020.

### Features

- Depth First Execution with Mapping on Dask - [#2646](https://github.com/PrefectHQ/prefect/pull/2646)
- Support use of cloud storage with containerized environments - [#2517](https://github.com/PrefectHQ/prefect/issues/2517),[#2796](https://github.com/PrefectHQ/prefect/pull/2796)

### Enhancements

- Add flag to include hostname on local storage - [#2653](https://github.com/PrefectHQ/prefect/issues/2653)
- Add option to set `image_pull_secret` directly on `DaskKubernetesEnvironment` - [#2657](https://github.com/PrefectHQ/prefect/pull/2657)
- Allow for custom callables for Result locations - [#2577](https://github.com/PrefectHQ/prefect/issues/2577)
- Ensure all Parameter values, included non-required defaults, are present in context - [#2698](https://github.com/PrefectHQ/prefect/pull/2698)
- Use absolute path for `LocalResult` location for disambiguation - [#2698](https://github.com/PrefectHQ/prefect/pull/2698)
- Retry client requests when receiving an `API_ERROR` code in the response - [#2705](https://github.com/PrefectHQ/prefect/pull/2705)
- Reduce size of serialized tasks when running on Dask - [#2707](https://github.com/PrefectHQ/prefect/pull/2707)
- Extend run state signatures for future development - [#2718](https://github.com/PrefectHQ/prefect/pull/2718)
- Update set_flow_run_state for future meta state use - [#2725](https://github.com/PrefectHQ/prefect/pull/2725)
- Add an optional `flow` argument to `merge` to support using it when not inside a flow context - [#2727](https://github.com/PrefectHQ/prefect/pull/2727)
- Add option to set service account name on Prefect jobs created by Kubernetes agent - [#2547](https://github.com/PrefectHQ/prefect/issues/2547)
- Add option to set imagePullPolicy on Prefect jobs created by Kubernetes agent - [#2721](https://github.com/PrefectHQ/prefect/issues/2721)
- Add option to set API url on agent start CLI command - [#2633](https://github.com/PrefectHQ/prefect/issues/2633)
- Add CI step to build `prefecthq/prefect:all_extras` Docker image for bundling all Prefect dependencies - [#2745](https://github.com/PrefectHQ/prefect/pull/2745)
- Move `Parameter` to a standalone module - [#2758](https://github.com/PrefectHQ/prefect/pull/2758)
- Validate Cached states based on hashed inputs - [#2763](https://github.com/PrefectHQ/prefect/pull/2763)
- Add `validate_configuration` utility to Fargate Agent for verifying it can manage tasks properly - [#2768](https://github.com/PrefectHQ/prefect/pull/2768)
- Add option to specify task targets as callables - [#2769](https://github.com/PrefectHQ/prefect/pull/2769)
- Improve `State.__repr__` when there is no message - [#2773](https://github.com/PrefectHQ/prefect/pull/2773)
- Add support for db argument at run time in the SQLiteQuery and SQLiteScript - [#2782](https://github.com/PrefectHQ/prefect/pull/2782)
- Add support for mapped argument in control flows - [#2784](https://github.com/PrefectHQ/prefect/pull/2784)
- Use pagination in kubernetes resource manager to reduce memory usage - [#2794](https://github.com/PrefectHQ/prefect/pull/2794)

### Task Library

- Adds a task to expose Great Expectations checkpoints as a node in a Prefect pipeline - [#2489](https://github.com/PrefectHQ/prefect/issues/2489)

### Server

- None

### Fixes

- Fix flow.visualize cleanup of source files when using `filename` - [#2726](https://github.com/PrefectHQ/prefect/issues/2726)
- Fix `S3Result` handling of AWS credentials provided through kwargs - [#2747](https://github.com/PrefectHQ/prefect/issues/2747)
- Fix `DaskKubernetesEnvironment` requiring that an `env` block is set when using custom specs - [#2657](https://github.com/PrefectHQ/prefect/pull/2657)
- Fix `PostgresExecute` task auto commit when commit is set to `False` - [#2658](https://github.com/PrefectHQ/prefect/issue/2658)
- Remove need for `{filename}` in mapped templates - [#2640](https://github.com/PrefectHQ/prefect/issues/2640)
- Fix issue with Results erroring out on multi-level mapped pipelines - [#2716](https://github.com/PrefectHQ/prefect/issues/2716)
- Fix issue with dask resource tags not being respected - [#2735](https://github.com/PrefectHQ/prefect/pull/2735)
- Ensure state deserialization works even when another StateSchema exists - [#2738](https://github.com/PrefectHQ/prefect/pull/2738)
- Remove implicit payload size restriction from Apollo - [#2764](https://github.com/PrefectHQ/prefect/pull/2764)
- Fix issue with declared storage secrets in K8s job environment and Dask K8s environment - [#2780](https://github.com/PrefectHQ/prefect/pull/2780)
- Fix context handling for Cloud when working with in-process retries - [#2783](https://github.com/PrefectHQ/prefect/pull/2783)

### Deprecations

- Accessing `prefect.core.task.Parameter` is deprecated in favor of `prefect.core.parameter.Parameter` - [#2758](https://github.com/PrefectHQ/prefect/pull/2758)

### Breaking Changes

- Environment `setup` and `execute` function signatures now accept Flow objects - [#2796](https://github.com/PrefectHQ/prefect/pull/2796)
- `create_flow_run_job` logic has been moved into `execute` for `DaskKubernetesEnvironment` and `KubernetesJobEnvironment` - [#2796](https://github.com/PrefectHQ/prefect/pull/2796)

### Contributors

- [Alex Cano](https://github.com/alexisprince1994)
- [David Haines](https://github.com/davidfhaines)
- [Paweł Cieśliński](https://github.com/pcieslinski)

## 0.11.5 <Badge text="beta" type="success" />

Released on June 2, 2020.

### Features

- None

### Enhancements

- Allow for manual approval of locally Paused tasks - [#2693](https://github.com/PrefectHQ/prefect/issues/2693)
- Task instances define a `__signature__` attribute, for improved introspection and tab-completion - [#2602](https://github.com/PrefectHQ/prefect/pull/2602)
- Tasks created with `@task` forward the wrapped function's docstring - [#2602](https://github.com/PrefectHQ/prefect/pull/2602)
- Support creating temporary dask clusters from within a `DaskExecutor` - [#2667](https://github.com/PrefectHQ/prefect/pull/2667)
- Add option for setting any build kwargs on Docker storage - [#2668](https://github.com/PrefectHQ/prefect/pull/2668)
- Add flow run ID option to `get logs` CLI command - [#2671](https://github.com/PrefectHQ/prefect/pull/2671)
- Add ID to output of `get` command for `flows` and `flow-runs` - [#2671](https://github.com/PrefectHQ/prefect/pull/2671)

### Task Library

- None

### Server

- None

### Fixes

- Fix issue with Google imports being tied together - [#2661](https://github.com/PrefectHQ/prefect/issues/2661)
- Don't warn about unused tasks defined inline and copied - [#2677](https://github.com/PrefectHQ/prefect/issues/2677)
- Remove unnecessary volume mount from dev infrastructure Docker compose - [#2676](https://github.com/PrefectHQ/prefect/issues/2676)
- Fix issue with instantiating LocalResult on Windows with dir from other drive - [#2683](https://github.com/PrefectHQ/prefect/issues/2683)
- Fix invalid IP address error when running `server start` on Ubuntu using rootless Docker - [#2691](https://github.com/PrefectHQ/prefect/pull/2691)

### Deprecations

- Deprecate `local_processes` and `**kwargs` arguments for `DaskExecutor` - [#2667](https://github.com/PrefectHQ/prefect/pull/2667)
- Deprecate `address='local'` for `DaskExecutor` - [#2667](https://github.com/PrefectHQ/prefect/pull/2667)

### Breaking Changes

- None

### Contributors

- [Alex Cano](https://github.com/alexisprince1994)

## 0.11.4 <Badge text="beta" type="success" />

Released on May 27, 2020.

### Fixes

- Revert GraphQL endpoint change - [#2660](https://github.com/PrefectHQ/prefect/pull/2660)

## 0.11.3 <Badge text="beta" type="success" />

Released on May 27, 2020.

### Features

- None

### Enhancements

- Add option to set volumes on `server start` CLI command - [#2560](https://github.com/PrefectHQ/prefect/pull/2560)
- Add `case` to top-level namespace - [#2609](https://github.com/PrefectHQ/prefect/pull/2609)
- Use host IP for `hostname` label in cases where `LocalAgent` is in container using host network - [#2618](https://github.com/PrefectHQ/prefect/issues/2618)
- Add option to set TLS configuration on client created by Docker storage - [#2626](hhttps://github.com/PrefectHQ/prefect/issues/2626)
- The `start_time` of a `Paused` state defaults to `None` - [#2617](https://github.com/PrefectHQ/prefect/pull/2617)
- Raise more informative error when Cloud Secret doesn't exist - [#2620](https://github.com/PrefectHQ/prefect/pull/2620)
- Update GraphQL endpoint to `/graphql` - [#2651](https://github.com/PrefectHQ/prefect/pull/2651)

### Task Library

- None

### Fixes

- Kubernetes agent resource manager is more strict about what resources it manages - [#2641](https://github.com/PrefectHQ/prefect/pull/2641)
- Fix error when adding `Parameter` to flow under `case` statement - [#2608](https://github.com/PrefectHQ/prefect/pull/2608)
- Fix `S3Result` attempting to load data when checking existence - [#2623](https://github.com/PrefectHQ/prefect/issues/2623)

### Deprecations

- Deprecate `private_registry` and `docker_secret` options on `DaskKubernetesEnvironment` - [#2630](https://github.com/PrefectHQ/prefect/pull/2630)

### Breaking Changes

- Kubernetes labels associated with Prefect flow runs now have a `prefect.io/` prefix (e.g. `prefect.io/identifier`) - [#2641](https://github.com/PrefectHQ/prefect/pull/2641)

### Contributors

- [Bartek Roszak](https://github.com/BartekRoszak)
- [James Lamb](https://github.com/jameslamb)

## 0.11.2 <Badge text="beta" type="success"/>

Released on May 19, 2020.

### Features

- None

### Enhancements

- Allow log configuration in Fargate Agent - [#2589](https://github.com/PrefectHQ/prefect/pull/2589)
- Reuse `prefect.context` for opening `Flow` contexts - [#2581](https://github.com/PrefectHQ/prefect/pull/2581)
- Show a warning when tasks are created in a flow context but not added to a flow - [#2584](https://github.com/PrefectHQ/prefect/pull/2584)

### Server

- Add API healthcheck tile to the UI - [#2395](https://github.com/PrefectHQ/prefect/issues/2395)

### Task Library

- None

### Fixes

- Fix type for Dask Security in RemoteDaskEnvironment - [#2571](https://github.com/PrefectHQ/prefect/pull/2571)
- Fix issue with `log_stdout` not correctly storing returned data on the task run state - [#2585](https://github.com/PrefectHQ/prefect/pull/2585)
- Ensure result locations are updated from targets when copying tasks with `task_args` - [#2590](https://github.com/PrefectHQ/prefect/pull/2590)
- Fix `S3Result` exists function handling of `NoSuchKey` error - [#2585](https://github.com/PrefectHQ/prefect/issues/2585)
- Fix confusing language in Telemetry documentation - [#2593](https://github.com/PrefectHQ/prefect/pull/2593)
- Fix `LocalAgent` not registering with Cloud using default labels - [#2587](https://github.com/PrefectHQ/prefect/issues/2587)
- Fix flow's `run_agent` function passing a `set` of labels to Agent instead of a `list` - [#2600](https://github.com/PrefectHQ/prefect/pull/2600)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Joe Schmid](https://github.com/joeschmid)

## 0.11.1 <Badge text="beta" type="success"/>

Released on May 15, 2020.

### Fixes

- Fix duplicate agent label literal eval parsing - [#2569](https://github.com/PrefectHQ/prefect/issues/2569)

## 0.11.0 <Badge text="beta" type="success"/>

Released on May 14, 2020.

### Features

- Introducing new [Results](https://docs.prefect.io/core/concepts/results.html) interface for working with task results - [#2507](https://github.com/PrefectHQ/prefect/pull/2507)

### Enhancements

- Allow slack_task to accept a dictionary for the message parameter to build a specially-structured JSON Block - [#2541](https://github.com/PrefectHQ/prefect/pull/2541)
- Support using `case` for control flow with the imperative api - [#2546](https://github.com/PrefectHQ/prefect/pull/2546)
- `flow.visualize` is now able to accept a `format` argument to specify the output file type - [#2447](https://github.com/PrefectHQ/prefect/issues/2447)
- Docker storage now writes flows to `/opt` dir to remove need for root permissions - [#2025](https://github.com/PrefectHQ/prefect/issues/2025)
- Add option to [set secrets on Storage objects](https://docs.prefect.io/orchestration/recipes/third_party_auth.html#declaring-secrets-on-storage) - [#2507](https://github.com/PrefectHQ/prefect/pull/2507)
- Add reserved [default Secret names](https://docs.prefect.io/orchestration/recipes/third_party_auth.html#list-of-default-secret-names) and formats for working with cloud platforms - [#2507](https://github.com/PrefectHQ/prefect/pull/2507)
- Add unique naming option to the jobs created by the `KubernetesJobEnvironment` - [#2553](https://github.com/PrefectHQ/prefect/pull/2553)
- Use `ast.literal_eval` for configuration values - [#2536](https://github.com/PrefectHQ/prefect/issues/2536)
- Prevent local cycles even if flow validation is deferred - [#2565](https://github.com/PrefectHQ/prefect/pull/2565)

### Server

- Add "cancellation-lite" semantic by preventing task runs from running if the flow run isn't running - [#2535](https://github.com/PrefectHQ/prefect/pull/2535)
- Add minimal telemetry to Prefect Server - [#2467](https://github.com/PrefectHQ/prefect/pull/2467)

### Task Library

- Add tasks to create issues for Jira and Jira Service Desk [#2431](https://github.com/PrefectHQ/prefect/pull/2431)
- Add `DbtShellTask`, an extension of ShellTask for working with data build tool (dbt) - [#2526](https://github.com/PrefectHQ/prefect/pull/2526)
- Add `prefect.tasks.gcp.bigquery.BigQueryLoadFile` - [#2423](https://github.com/PrefectHQ/prefect/issues/2423)

### Fixes

- Fix bug in Kubernetes agent `deployment.yaml` with a misconfigured liveness probe - [#2519](https://github.com/PrefectHQ/prefect/pull/2519)
- Fix checkpointing feature not being able to be disabled when using server backend - [#2438](https://github.com/PrefectHQ/prefect/issues/2438)

### Deprecations

- Result Handlers are now deprecated in favor of the new Result interface - [#2507](https://github.com/PrefectHQ/prefect/pull/2507)

### Breaking Changes

- Allow for setting docker daemon at build time using DOCKER_HOST env var to override base_url in docker storage - [#2482](https://github.com/PrefectHQ/prefect/pull/2482)
- Ensure all calls to `flow.run()` use the same execution logic - [#1994](https://github.com/PrefectHQ/prefect/pull/1994)
- Moved `prefect.tasks.cloud` to `prefect.tasks.prefect` - [#2404](https://github.com/PrefectHQ/prefect/pull/2404)
- Trigger signature now accepts a dictionary of `[Edge, State]` to allow for more customizable trigger behavior - [#2298](https://github.com/PrefectHQ/prefect/issues/2298)
- Remove all uses of `credentials_secret` from task library in favor of `PrefectSecret` tasks - [#2507](https://github.com/PrefectHQ/prefect/pull/2507)
- Remove `Bytes` and `Memory` storage objects - [#2507](https://github.com/PrefectHQ/prefect/pull/2507)

### Contributors

- [Alvin Goh](https://github.com/chuehsien)
- [Daniel Kapitan](https://github.com/dkapitan)
- [Mark McDonald](https://github.com/mhmcdonald)
- [Jie Lou](https://github.com/JLouSRM)

## 0.10.7 <Badge text="beta" type="success"/>

Released on May 6, 2020.

### Features

- None

### Enhancements

- Agents now support an optional HTTP health check, for use by their backing orchestration layer (e.g. k8s, docker, supervisord, ...) - [#2406](https://github.com/PrefectHQ/prefect/pull/2406)
- Sets dask scheduler default to "threads" on LocalDaskExecutor to provide parallelism - [#2494](https://github.com/PrefectHQ/prefect/pull/2494)
- Enhance agent verbose logs to include provided kwargs at start - [#2486](https://github.com/PrefectHQ/prefect/issues/2486)
- Add `no_cloud_logs` option to all Agent classes for an easier way to disable sending logs to backend - [#2484](https://github.com/PrefectHQ/prefect/issues/2484)
- Add option to set flow run environment variables on Kubernetes agent install - [#2424](https://github.com/PrefectHQ/prefect/issues/2424)

### Task Library

- Add new `case` control-flow construct, for nicer management of conditional tasks - [#2443](https://github.com/PrefectHQ/prefect/pull/2443)

### Fixes

- Give a better error for non-serializable callables when registering with cloud/server - [#2491](https://github.com/PrefectHQ/prefect/pull/2491)
- Fix runners retrieving invalid `context.caches` on runs started directly from a flow runner - [#2403](https://github.com/PrefectHQ/prefect/issues/2403)

### Deprecations

- None

### Breaking Changes

- Remove the Nomad agent - [#2492](https://github.com/PrefectHQ/prefect/pull/2492)

### Contributors

- None

## 0.10.6 <Badge text="beta" type="success"/>

Released on May 5, 2020.

### Features

- Add DaskCloudProviderEnvironment to dynamically launch Dask clusters, e.g. on AWS Fargate - [#2360](https://github.com/PrefectHQ/prefect/pull/2360)

### Enhancements

- Add `botocore_config` option to Fargate agent for setting botocore configuration when interacting with boto3 client - [#2170](https://github.com/PrefectHQ/prefect/issues/2170)
- Don't create a `None` task for a null condition when using `ifelse` - [#2449](https://github.com/PrefectHQ/prefect/pull/2449)
- Add support for EC2 launch type in Fargate Agent and `FargateTaskEnvironment` - [#2421](https://github.com/PrefectHQ/prefect/pull/2421)
- Add `flow_id` to context for Flow runs - [#2461](https://github.com/PrefectHQ/prefect/pull/2461)
- Allow users to inject custom context variables into their logger formats - [#2462](https://github.com/PrefectHQ/prefect/issues/2462)
- Add option to set backend on `agent install` CLI command - [#2478](https://github.com/PrefectHQ/prefect/pull/2478)

### Task Library

- None

### Fixes

- Fix `start_server.sh` script when an env var is undefined - [#2450](https://github.com/PrefectHQ/prefect/pull/2450)
- Fix `server start` CLI command not respecting `version` kwarg on tagged releases - [#2435](https://github.com/PrefectHQ/prefect/pull/2435)
- Fix issue with non-JSON serializable args being used to format log messages preventing them from shipping to Cloud - [#2407](https://github.com/PrefectHQ/prefect/issues/2407)
- Fix issue where ordered Prefect collections use lexical sorting, not numerical sorting, which can result in unexpected ordering - [#2452](https://github.com/PrefectHQ/prefect/pull/2452)
- Fix issue where Resource Manager was failing due to non-JSON timestamp in log writing - [#2474](https://github.com/PrefectHQ/prefect/issues/2474)
- Fix periodic error in local agent process management loop - [#2419](https://github.com/PrefectHQ/prefect/issues/2419)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Grégory Duchatelet](https://github.com/gregorg)
- [Joe Schmid](https://github.com/joeschmid)

## 0.10.5 <Badge text="beta" type="success"/>

Released on Apr 28, 2020.

### Features

- None

### Enhancements

- Added serializer for `RemoteDaskEnvironment` - [#2369](https://github.com/PrefectHQ/prefect/issues/2369)
- `server start` CLI command now defaults to image build based on current Prefect installation version - [#2375](https://github.com/PrefectHQ/prefect/issues/2375)
- Add option to set `executor_kwargs` on `KubernetesJobEnvironment` and `FargateTaskEnvironment` - [#2258](https://github.com/PrefectHQ/prefect/issues/2258)
- Add map index to task logs for mapped task runs - [#2402](https://github.com/PrefectHQ/prefect/pull/2402)
- Agents can now register themselves with Cloud for better management - [#2312](https://github.com/PrefectHQ/prefect/issues/2312)
- Adding support for `environment`, `secrets`, and `mountPoints` via configurable `containerDefinitions` to the Fargate Agent - [#2397](https://github.com/PrefectHQ/prefect/pull/2397)
- Add flag for disabling Docker agent interface check on Linux - [#2361](https://github.com/PrefectHQ/prefect/issues/2361)

### Task Library

- Add Pushbullet notification task to send notifications to mobile - [#2366](https://github.com/PrefectHQ/prefect/pull/2366)
- Add support for Docker volumes and filtering in `prefect.tasks.docker` - [#2384](https://github.com/PrefectHQ/prefect/pull/2384)

### Fixes

- Fix Docker storage path issue when registering flows on Windows machines - [#2332](https://github.com/PrefectHQ/prefect/issues/2332)
- Fix issue with refreshing Prefect Cloud tokens - [#2409](https://github.com/PrefectHQ/prefect/pull/2409)
- Resolve invalid escape sequence deprecation warnings - [#2414](https://github.com/PrefectHQ/prefect/issues/2414)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Nelson Cornet](https://github.com/sk4la)
- [Braun Reyes](https://github.com/braunreyes)
- [Fraznist](https://github.com/Fraznist)
- [sk4la](https://github.com/sk4la)
- [Troy Köhler](https://github.com/trkohler)

## 0.10.4 <Badge text="beta" type="success"/>

Released on Apr 21, 2020.

### Enhancements

- Agent connection step shows which endpoint it is connected to and checks API connectivity - [#2372](https://github.com/PrefectHQ/prefect/pull/2372)

### Breaking Changes

- Revert changes to `ifelse` & `switch` (added in [#2310](https://github.com/PrefectHQ/prefect/pull/2310)), removing implicit
  creation of `merge` tasks - [#2379](https://github.com/PrefectHQ/prefect/pull/2379)

## 0.10.3 <Badge text="beta" type="success"/>

Released on Apr 21, 2020.

### Features

- None

### Enhancements

- Allow GraphQL endpoint configuration via `config.toml` for remote deployments of the UI - [#2338](https://github.com/PrefectHQ/prefect/pull/2338)
- Add option to connect containers created by Docker agent to an existing Docker network - [#2334](https://github.com/PrefectHQ/prefect/pull/2334)
- Expose `datefmt` as a configurable logging option in Prefect configuration - [#2340](https://github.com/PrefectHQ/prefect/pull/2340)
- The Docker agent configures containers to auto-remove on completion - [#2347](https://github.com/PrefectHQ/prefect/pull/2347)
- Use YAML's safe load and dump commands for the `server start` CLI command - [#2352](https://github.com/PrefectHQ/prefect/pull/2352)
- New `RemoteDaskEnvironment` specifically for running Flows on an existing Dask cluster - [#2367](https://github.com/PrefectHQ/prefect/pull/2367)

### Task Library

- None

### Fixes

- Fix `auth create-token` CLI command specifying deprecated `role` instead of `scope` - [#2336](https://github.com/PrefectHQ/prefect/issues/2336)
- Fix local schedules not continuing to schedule on errors outside of runner's control - [#2133](https://github.com/PrefectHQ/prefect/issues/2133)
- Fix `get_latest_cached_states` pulling incorrect upstream cached states when using Core server as the backend - [#2343](https://github.com/PrefectHQ/prefect/issues/2343)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Brad McElroy](https://github.com/limx0)
- [Joe Schmid](https://github.com/joeschmid)

## 0.10.2 <Badge text="beta" type="success"/>

Released on Apr 14, 2020.

### Features

- None

### Enhancements

- Task logical operators (e.g. `And`, `Or`, ...) no longer implicitly cast to `bool` - [#2303](https://github.com/PrefectHQ/prefect/pull/2303)
- Allow for dynamically changing secret names at runtime - [#2302](https://github.com/PrefectHQ/prefect/pull/2302)
- Update `ifelse` and `switch` to return tasks representing the output of the run branch - [#2310](https://github.com/PrefectHQ/prefect/pull/2310)

### Task Library

- Rename the base secret tasks for clarity - [#2302](https://github.com/PrefectHQ/prefect/pull/2302)

### Fixes

- Fix possible subprocess deadlocks when sending stdout to `subprocess.PIPE` - [#2293](https://github.com/PrefectHQ/prefect/pull/2293), [#2295](https://github.com/PrefectHQ/prefect/pull/2295)
- Fix issue with Flow registration to non-standard Cloud backends - [#2292](https://github.com/PrefectHQ/prefect/pull/2292)
- Fix issue with registering Flows with Server that have required scheduled Parameters - [#2296](https://github.com/PrefectHQ/prefect/issues/2296)
- Fix interpolation of config for dev services CLI for Apollo - [#2299](https://github.com/PrefectHQ/prefect/pull/2299)
- Fix pytest Cloud and Core server backend fixtures - [#2319](https://github.com/PrefectHQ/prefect/issues/2319)
- Fix `AzureResultHandler` choosing an empty Secret over provided connection string - [#2316](https://github.com/PrefectHQ/prefect/issues/2316)
- Fix containers created by Docker agent not being able to reach out to host API - [#2324](https://github.com/PrefectHQ/prefect/issues/2324)

### Deprecations

- None

### Breaking Changes

- Remove `env_var` initialization from `EnvVarSecret` in favor of `name` - [#2302](https://github.com/PrefectHQ/prefect/pull/2302)

### Contributors

- [Brad McElroy](https://github.com/limx0)

## 0.10.1 <Badge text="beta" type="success"/>

Released on Apr 7, 2020.

### Features

- CI build for prefect server images - [#2229](https://github.com/PrefectHQ/prefect/pull/2229), [#2275](https://github.com/PrefectHQ/prefect/issues/2275)
- Allow kwargs to boto3 in S3ResultHandler - [#2240](https://github.com/PrefectHQ/prefect/issues/2240)

### Enhancements

- Add flags to `prefect server start` for disabling service port mapping - [#2228](https://github.com/PrefectHQ/prefect/pull/2228)
- Add options to `prefect server start` for mapping to host ports - [#2228](https://github.com/PrefectHQ/prefect/pull/2228)
- Return `flow_run_id` from CLI `run` methods for programmatic use - [#2242](https://github.com/PrefectHQ/prefect/pull/2242)
- Add JSON output option to `describe` CLI commands - [#1813](https://github.com/PrefectHQ/prefect/issues/1813)
- Add ConstantResult for eventually replacing ConstantResultHandler - [#2145](https://github.com/PrefectHQ/prefect/issues/2145)
- Add new `diagnostics` mode for timing requests made to Cloud - [#2283](https://github.com/PrefectHQ/prefect/pull/2283)

### Task Library

- Make `project_name` optional for `FlowRunTask` to allow for use with Prefect Core's server - [#2266](https://github.com/PrefectHQ/prefect/pull/2266)
- Adds `prefect.tasks.docker.container.RemoveContainer`

### Fixes

- Fix `S3ResultHandler` safe retrieval of `_client` attribute - [#2232](https://github.com/PrefectHQ/prefect/issues/2232)
- Change default log `timestamp` value in database to be identical to other tables instead of a hard coded value - [#2230](https://github.com/PrefectHQ/prefect/pull/2230)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Manuel Aristarán](https://github.com/jazzido)
- [szelenka](https://github.com/szelenka)
- [Aditya Bhumbla](https://github.com/abhumbla)
- [Alex Cano](https://github.com/alexisprince1994)

## 0.10.0 <Badge text="beta" type="success"/>

Released on Mar 29, 2020.

### Features

- Open source database backend, GraphQL API and UI - [#2218](https://github.com/PrefectHQ/prefect/pull/2218)
- Add `prefect server start` CLI command for spinning up database and UI - [#2214](https://github.com/PrefectHQ/prefect/pull/2214)

### Enhancements

- Add ValidationFailed state and signal in anticipation of validating task outputs - [#2143](https://github.com/PrefectHQ/prefect/issues/2143)
- Add max polling option to all agents - [#2037](https://github.com/PrefectHQ/prefect/issues/2037)
- Add GCSResult type [#2141](https://github.com/PrefectHQ/prefect/issues/2141)
- Add Result.validate method that runs validator functions initialized on Result [#2144](https://github.com/PrefectHQ/prefect/issues/2144)
- Convert all GraphQL calls to have consistent casing - [#2185](https://github.com/PrefectHQ/prefect/pull/2185) [#2198](https://github.com/PrefectHQ/prefect/pull/2198)
- Add `prefect backend` CLI command for switching between Prefect Core server and Prefect Cloud - [#2203](https://github.com/PrefectHQ/prefect/pull/2203)
- Add `prefect run server` CLI command for starting flow runs without use of project name - [#2203](https://github.com/PrefectHQ/prefect/pull/2203)
- Make `project_name` optional during flow registration to support Prefect Core's server - [#2203](https://github.com/PrefectHQ/prefect/pull/2203)
- Send flow run and task run heartbeat at beginning of run time - [#2203](https://github.com/PrefectHQ/prefect/pull/2203)

### Task Library

- None

### Fixes

- Fix issue with heartbeat failing if any Cloud config var is not present - [#2190](https://github.com/PrefectHQ/prefect/issues/2190)
- Fix issue where `run cloud` CLI command would pull final state before last batch of logs - [#2192](https://github.com/PrefectHQ/prefect/pull/2192)
- Fix issue where the `S3ResultHandler` would attempt to access uninitialized attribute - [#2204](https://github.com/PrefectHQ/prefect/issues/2204)

### Deprecations

- None

### Breaking Changes

- Drop support for Python 3.5 - [#2191](https://github.com/PrefectHQ/prefect/pull/2191)
- Remove `Client.write_run_log` - [#2184](https://github.com/PrefectHQ/prefect/issues/2184)
- Remove `Client.deploy` and `flow.deploy` - [#2183](https://github.com/PrefectHQ/prefect/issues/2183)

### Contributors

- None

## 0.9.8

Released on Mar 18, 2020.

### Features

- None

### Enhancements

- Update Cloud config name for heartbeat settings - [#2081](https://github.com/PrefectHQ/prefect/pull/2081)
- Add examples to Interactive API Docs - [#2122](https://github.com/PrefectHQ/prefect/pull/2122)
- Allow users to skip Docker healthchecks - [#2150](https://github.com/PrefectHQ/prefect/pull/2150)
- Add exists, read, and write interfaces to Result [#2139](https://github.com/PrefectHQ/prefect/issues/2139)
- Add Cloud UI links to Slack Notifications - [#2112](https://github.com/PrefectHQ/prefect/issues/2112)

### Task Library

- None

### Fixes

- Fix S3ResultHandler use of a new boto3 session per thread - [#2108](https://github.com/PrefectHQ/prefect/issues/2108)
- Fix issue with stateful function reference deserialization logic mutating state - [#2159](https://github.com/PrefectHQ/prefect/pull/2159)
- Fix issue with `DateClock` serializer - [#2166](https://github.com/PrefectHQ/prefect/issues/2166)
- Fix issue with scheduling required parameters - [#2166](https://github.com/PrefectHQ/prefect/issues/2166)

### Deprecations

- Deprecate cache\_\* and result_handler options on Task and Flow objects [#2140](https://github.com/PrefectHQ/prefect/issues/2140)

### Breaking Changes

- None

### Contributors

- [alexisprince1994](https://github.com/alexisprince1994)

## 0.9.7 <Badge text="beta" type="success"/>

Released on Mar 4, 2020.

### Fixes

- Change `task.log_stdout` retrieval from task runner to `getattr` in order to preserve running flows of older 0.9.x versions - [#2120](https://github.com/PrefectHQ/prefect/pull/2120)

## 0.9.6 <Badge text="beta" type="success"/>

Released on Mar 4, 2020.

### Features

- Add new diagnostics utility to assist in troubleshooting issues - [#2062](https://github.com/PrefectHQ/prefect/pull/2062)
- Add a jira_notification state handler to create jira tickets for failed tasks or flows - [#1861](https://github.com/PrefectHQ/prefect/pull/1861)
- Add support for Python 3.8 - [#2080](https://github.com/PrefectHQ/prefect/pull/2080)

### Enhancements

- Add PIN 15 (skip refactor) - [#2070](https://github.com/PrefectHQ/prefect/issues/2070)
- Update docs and docstrings related to Result Handlers - [#1792](https://github.com/PrefectHQ/prefect/issues/1792)
- Add volume option to Docker Agent - [#2013](https://github.com/PrefectHQ/prefect/issues/2013)
- `DaskKubernetesEnvironment` now elevates important autoscaling logs as well as possible Kubernetes issues - [#2089](https://github.com/PrefectHQ/prefect/pull/2089)
- Add optional `scheduler_logs` kwarg to the`DaskKubernetesEnvironment` - [#2089](https://github.com/PrefectHQ/prefect/pull/2089)
- Add ERROR log if heartbeat process dies - [#2097](https://github.com/PrefectHQ/prefect/issues/2097)
- Enable stdout logging from inside a task with the kwarg `log_stdout=True` - [#2092](https://github.com/PrefectHQ/prefect/pull/2092)
- Direct links to Cloud flows and flow runs now shown on creation time - [#2109](https://github.com/PrefectHQ/prefect/pull/2109)
- Update docs related to using Context - [#2077](https://github.com/PrefectHQ/prefect/issues/2077)

### Task Library

- Fix expanding of `V1DeleteOptions` kwargs for Kubernetes tasks - [#2083](https://github.com/PrefectHQ/prefect/pull/2083)

### Fixes

- Fix `extra_loggers` config variable not being able to be set via environment variable - [#2089](https://github.com/PrefectHQ/prefect/pull/2089)
- Fix environments not passing down their `extra_loggers` to any created infrastructure - [#2089](https://github.com/PrefectHQ/prefect/pull/2089)
- Don't mutate data when serializing or deserializing - [#2098](https://github.com/PrefectHQ/prefect/issues/2098)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Romain Thalineau](https://github.com/romaintha)

## 0.9.5 <Badge text="beta" type="success"/>

Released on Feb 21, 2020.

### Features

- None

### Enhancements

- Better exception for unsubscriptable mapping arguments - [#1821](https://github.com/PrefectHQ/prefect/issues/1821)
- Upload package to PyPI on tag push to master - [#2030](https://github.com/PrefectHQ/prefect/issues/2030)
- Add DaskGateway tip to docs - [#1959](https://github.com/PrefectHQ/prefect/issues/1959)
- Improve package import time - [#2046](https://github.com/PrefectHQ/prefect/issues/2046)

### Task Library

- Fix `V1DeleteOptions` call for Kubernetes tasks - [#2050](https://github.com/PrefectHQ/prefect/pull/2050)
- Add kwargs to `V1DeleteOptions` for Kubernetes tasks - [#2051](https://github.com/PrefectHQ/prefect/pull/2051)

### Fixes

- Ensure microseconds are respected on `start_date` provided to CronClock - [#2031](https://github.com/PrefectHQ/prefect/pull/2031)
- Fix duplicate Client connections when using `--logs` flag from `run cloud` CLI command - [#2056](https://github.com/PrefectHQ/prefect/pull/2056)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Romain Thalineau](https://github.com/romaintha)

## 0.9.4 <Badge text="beta" type="success"/>

Released on Feb 14, 2020.

### Features

- None

### Enhancements

- Add incremental tutorial - [#1953](https://github.com/PrefectHQ/prefect/issues/1953)
- Improve error handling for unsupported callables - [#1993](https://github.com/PrefectHQ/prefect/pull/1993)
- Accept additional `boto3` client parameters in S3 storage - [#2000](https://github.com/PrefectHQ/prefect/pull/2000)
- Add optional `version_group_id` kwarg to `create_flow_run` for a stable API for flow runs - [#1987](https://github.com/PrefectHQ/prefect/issues/1987)
- Add `extra_loggers` logging configuration for non-Prefect logs in stdout and cloud - [#2010](https://github.com/PrefectHQ/prefect/pull/2010)

### Task Library

- None

### Fixes

- Ensure `ifelse` casts its condition to `bool` prior to evaluation - [#1991](https://github.com/PrefectHQ/prefect/pull/1991)
- Do not perform `ast.literal_eval` on cpu and memory task_definition kwargs for Fargate Agent - [#2010](https://github.com/PrefectHQ/prefect/pull/2010)
- Fix new agent processing with Threadpool causing problem for Fargate Agent with task revisions enabled - [#2022](https://github.com/PrefectHQ/prefect/pull/2022)

### Deprecations

- None

### Breaking Changes

- Remove Airflow Tasks - [#1992](https://github.com/PrefectHQ/prefect/pull/1992)

### Contributors

- [Giorgio Pellero](https://github.com/trapped)
- [Braun Reyes](https://github.com/braunreyes)

## 0.9.3 <Badge text="beta" type="success"/>

Released on Feb 05, 2020.

### Features

- None

### Enhancements

- Improve heartbeat functionality to be robust across platforms - [#1973](https://github.com/PrefectHQ/prefect/pull/1973)
- Run storage healthchecks on other options besides Docker - [1963](https://github.com/PrefectHQ/prefect/pull/1963)
- Cloud logger now attempts to elevate logger errors to flow run logs - [#1961](https://github.com/PrefectHQ/prefect/pull/1961)
- Attach Flow and Task attributes to LogRecords - [#1938](https://github.com/PrefectHQ/prefect/issues/1938)

### Task Library

- None

### Fixes

- Fix uncaught Fargate Agent kwarg parse SyntaxError from `literal_eval` - [#1968](https://github.com/PrefectHQ/prefect/pull/1968)
- Fix FargateTaskEnvironment passing empty auth token to run task - [#1976](https://github.com/PrefectHQ/prefect/pull/1976)
- Fix imagePullSecrets not being automatically passed to jobs created by Kubernetes Agent - [#1982](https://github.com/PrefectHQ/prefect/pull/1982)

### Deprecations

- None

### Breaking Changes

- Remove cancellation hooks - [#1973](https://github.com/PrefectHQ/prefect/pull/1973)

### Contributors

- None

## 0.9.2 <Badge text="beta" type="success"/>

Released on Jan 30, 2020.

### Features

- Allow for parameter defaults to vary based on clock - [#1946](https://github.com/PrefectHQ/prefect/pull/1946)

### Enhancements

- More graceful handling of Agents competing for work - [#1956](https://github.com/PrefectHQ/prefect/issues/1956)

### Task Library

- None

### Fixes

- Eliminated possible duplicate flow run issue in all agents - [#1956](https://github.com/PrefectHQ/prefect/issues/1956)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- None

## 0.9.1 <Badge text="beta" type="success"/>

Released on Jan 24, 2020.

### Features

- None

### Enhancements

- Docker daemon reconnect attempts + exit on heartbeat failure -[#1918](https://github.com/PrefectHQ/prefect/pull/1918)
- More responsive agent shutdown - [#1921](https://github.com/PrefectHQ/prefect/pull/1921)
- Background all agent flow deployment attempts - [#1928](https://github.com/PrefectHQ/prefect/pull/1928)
- Add show_flow_logs to Docker agent [#1929](https://github.com/PrefectHQ/prefect/issues/1929)
- Add per-task checkpointing opt-out - [#1933](https://github.com/PrefectHQ/prefect/pull/1933)
- The Task 'checkpoint' kwarg will no longer be deprecated to allow opt-out - [#1933](https://github.com/PrefectHQ/prefect/pull/1933)

### Task Library

- None

### Fixes

- Fix the Fargate Agent not parsing kwargs as literals - [#1926](https://github.com/PrefectHQ/prefect/pull/1926)
- Fix issue with result handler default persisting from initialization - [#1936](https://github.com/PrefectHQ/prefect/issues/1936)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- None

## 0.9.0 <Badge text="beta" type="success"/>

Released on Jan 15, 2020.

### Features

- Added the ability to leverage native ECS task definition revisions for flow versions in Fargate agent - [#1870](https://github.com/PrefectHQ/prefect/pull/1870)
- Added the ability to pull in kwargs per flow version from S3 on flow submission in Fargate agent - [#1870](https://github.com/PrefectHQ/prefect/pull/1870)
- Add sensible default result handlers to non-Docker storage options - [#1888](https://github.com/PrefectHQ/prefect/issues/1888)

### Enhancements

- Allow for task looping to beyond Python's maximum recursion depth - [#1862](https://github.com/PrefectHQ/prefect/pull/1862)
- Prevent duplication of stdout logs from multiple instantiated agents - [#1866](https://github.com/PrefectHQ/prefect/pull/1866)
- Allow intervals less than 60 seconds in `IntervalClock`s - [#1880](https://github.com/PrefectHQ/prefect/pull/1880)
- Introduce new `Secret.exists` method for checking whether a Secret is available - [#1882](https://github.com/PrefectHQ/prefect/pull/1882)
- Introduce new `-e` CLI options on agent start commands to allow passing environment variables to flow runs - [#1878](https://github.com/PrefectHQ/prefect/issues/1878)
- Stop persisting `None` when calling result handlers - [#1894](https://github.com/PrefectHQ/prefect/pull/1894)
- Change Cancelled state to indicate Finished instead of Failed - [#1903](https://github.com/PrefectHQ/prefect/pull/1903)
- All States now store `cached_inputs` for easier recovery from failure - [#1898](https://github.com/PrefectHQ/prefect/issues/1898)
- Always checkpoint tasks which have result handlers - [#1898](https://github.com/PrefectHQ/prefect/issues/1898)

### Task Library

- Remove implicit requirement that Google Tasks use Prefect Cloud Secrets - [#1882](https://github.com/PrefectHQ/prefect/pull/1882)

### Fixes

- Enforce provision of `max_retries` if specifying `retry_delay` for a `Task` - [#1875](https://github.com/PrefectHQ/prefect/pull/1875)
- Fix issue with reduce tasks in `flow.visualize()` - [#1793](https://github.com/PrefectHQ/prefect/issues/1793)

### Deprecations

- The checkpointing kwarg will be removed from Tasks as it is now a default behavior - [#1898](https://github.com/PrefectHQ/prefect/issues/1898)

### Breaking Changes

- Remove default value for `aws_credentials_secret` on all S3 hooks - [#1886](https://github.com/PrefectHQ/prefect/issues/1886)
- Remove `config.engine.result_handler` section of Prefect config - [#1888](https://github.com/PrefectHQ/prefect/issues/1888)
- Remove default value for `credentials_secret` on `GCSResultHandler` - [#1888](https://github.com/PrefectHQ/prefect/issues/1888)
- Remove default value for `azure_credentials_secret` on `AzureResultHandler` - [#1888](https://github.com/PrefectHQ/prefect/issues/1888)

### Contributors

- [Daryll Strauss](daryll.strauss@gmail.com)
- [Braun Reyes](https://github.com/braunreyes)

## 0.8.1 <Badge text="beta" type="success"/>

Released on Dec 17, 2019.

### Features

- None

### Enhancements

- Enhanced treatment of nested and ordered constant values - [#1829](https://github.com/PrefectHQ/prefect/pull/1829)
- Add `on_datetime`, `on_date`, and `at_time` filters - [#1837](https://github.com/PrefectHQ/prefect/pull/1837)
- Add `--latest` flag for Kubernetes Agent install CLI command - [#1842](https://github.com/PrefectHQ/prefect/pull/1842)
- Add `--no-cloud-logs` flag for all agents to optionally opt-out of logs being sent to Prefect Cloud - [#1843](https://github.com/PrefectHQ/prefect/pull/1843)
- Agents mark Flow Runs as `Failed` if a deployment error occurs - [#1848](https://github.com/PrefectHQ/prefect/pull/1848)
- `Submitted` states from Agents include deployment identifier information - [#1848](https://github.com/PrefectHQ/prefect/pull/1848)
- Update heartbeats to respect Cloud flow settings - [#1851](https://github.com/PrefectHQ/prefect/pull/1851)
- Add flow run name to `prefect.context` - [#1855](https://github.com/PrefectHQ/prefect/pull/1855)
- Add `--namespace` option for Kubernetes Agent start CLI command - [#1859](https://github.com/PrefectHQ/prefect/pull/1859)
- Add Prefect job resource configuration for Kubernetes Agent - [#1859](https://github.com/PrefectHQ/prefect/pull/1859)

### Task Library

- Add task for scheduling a flow run - [#1871](https://github.com/PrefectHQ/prefect/pull/1871)

### Fixes

- Fix Agent deployment errors interrupting full list of found Flow Runs - [#1848](https://github.com/PrefectHQ/prefect/pull/1848)
- Fix issue with a single bad log preventing all logs from being sent to Cloud - [#1845](https://github.com/PrefectHQ/prefect/pull/1845)
- Fix Kubernetes Agent passing empty default namespace - [#1839](https://github.com/PrefectHQ/prefect/pull/1839)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- None

## 0.8.0 <Badge text="beta" type="success"/>

Released on Dec 11, 2019.

### Features

- Added new Local Agent to run Flows from Local Storage, S3 Storage, and GCS Storage - [#1819](https://github.com/PrefectHQ/prefect/pull/1819)
- Added Azure Blob Storage for Flows - [#1831](https://github.com/PrefectHQ/prefect/pull/1831)
- Added GCS Storage for Flows - [#1809](https://github.com/PrefectHQ/prefect/pull/1809)
- Added S3 Storage for Flows - [#1753](https://github.com/PrefectHQ/prefect/pull/1753)

### Enhancements

- Add `--rbac` flag to `prefect agent install` for Kubernetes Agent - [#1822](https://github.com/PrefectHQ/prefect/pull/1822)
- Add `prefect agent install` option to output `supervisord.conf` file for Local Agent - [#1819](https://github.com/PrefectHQ/prefect/pull/1819)
- Add convenience `parents()` and `children()` classmethods to all State objects for navigating the hierarchy - [#1784](https://github.com/PrefectHQ/prefect/pull/1784)
- Add new `not_all_skipped` trigger and set it as the default for merge tasks - [#1768](https://github.com/PrefectHQ/prefect/issues/1768)

### Task Library

- Azure Blob tasks now use newer `BlockBlobService` with connection string authentication - [#1831](https://github.com/PrefectHQ/prefect/pull/1831)

### Fixes

- Fix issue with `flow.visualize()` for mapped tasks which are skipped - [#1765](https://github.com/PrefectHQ/prefect/issues/1765)
- Fix issue with timeouts only being softly enforced - [#1145](https://github.com/PrefectHQ/prefect/issues/1145), [#1686](https://github.com/PrefectHQ/prefect/issues/1686)
- Log agent errors using `write_run_logs` instead of the deprecated `write_run_log` - [#1791](https://github.com/PrefectHQ/prefect/pull/1791)
- Fix issue with `flow.update()` not transferring constants - [#1785](https://github.com/PrefectHQ/prefect/pull/1785)

### Deprecations

- `flow.deploy` is deprecated in favor of `flow.register` - [#1819](https://github.com/PrefectHQ/prefect/pull/1819)

### Breaking Changes

- Default Flow storage is now `Local` instead of `Docker` - [#1819](https://github.com/PrefectHQ/prefect/pull/1819)
- Docker based `LocalAgent` is renamed `DockerAgent` - [#1819](https://github.com/PrefectHQ/prefect/pull/1819)
- `prefect agent start` now defaults to new `LocalAgent` - [#1819](https://github.com/PrefectHQ/prefect/pull/1819)

### Contributors

- None

## 0.7.3 <Badge text="beta" type="success"/>

Released on Nov 26, 2019.

### Features

- Add graceful cancellation hooks to Flow and Task runners - [#1758](https://github.com/PrefectHQ/prefect/pull/1758)

### Enhancements

- Add option to specify a run name for `cloud run` CLI command - [#1756](https://github.com/PrefectHQ/prefect/pull/1756)
- Add `work_stealing` option to `DaskKubernetesEnvironment` - [#1760](https://github.com/PrefectHQ/prefect/pull/1760)
- Improve heartbeat thread management - [#1770](https://github.com/PrefectHQ/prefect/pull/1770)
- Add unique scheduler Job name to `DaskKubernetesEnvironment` - [#1772](https://github.com/PrefectHQ/prefect/pull/1772)
- Add informative error when trying to map with the `LocalDaskExecutor` using processes - [#1777](https://github.com/PrefectHQ/prefect/pull/1777)

### Task Library

- None

### Fixes

- Fix issue with heartbeat thread deadlocking dask execution when using a `worker_client` - [#1750](https://github.com/PrefectHQ/prefect/pull/1750)
- Fix issue with Environments not calling `run_flow` on Environment stored on Flow object - [#1752](https://github.com/PrefectHQ/prefect/pull/1752)
- Fix issue with Docker build context when providing custom docker files - [#1762](https://github.com/PrefectHQ/prefect/pull/1762)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- None

## 0.7.2 <Badge text="beta" type="success"/>

Released on Nov 15, 2019.

### Features

- Allow users to provide a custom version group ID for controlling Cloud versioning - [#1665](https://github.com/PrefectHQ/prefect/issues/1665)
- Stop autogenerating constant tasks - [#1730](https://github.com/PrefectHQ/prefect/pull/1730)

### Enhancements

- Raise an informative error when context objects are pickled - [#1710](https://github.com/PrefectHQ/prefect/issues/1710)
- Add an option to pass in `run_name` to a flow run to override the auto-generated names when calling `create_flow_run` [#1661](https://github.com/PrefectHQ/cloud/pull/1661)
- Add informative logs in the event that a heartbeat thread dies - [#1721](https://github.com/PrefectHQ/prefect/pull/1721)
- Loosen Job spec requirements for `KubernetesJobEnvironment` - [#1713](https://github.com/PrefectHQ/prefect/pull/1713)
- Loosen `containerDefinitions` requirements for `FargateTaskEnvironment` - [#1713](https://github.com/PrefectHQ/prefect/pull/1713)
- Local Docker agent proactively fails flow runs if image cannot be pulled - [#1395](https://github.com/PrefectHQ/prefect/issues/1395)
- Add graceful keyboard interrupt shutdown for all agents - [#1731](https://github.com/PrefectHQ/prefect/pull/1731)
- `agent start` CLI command now allows for Agent kwargs - [#1737](https://github.com/PrefectHQ/prefect/pull/1737)
- Add users to specify a custom Dockerfile for Docker storage - [#1738](https://github.com/PrefectHQ/prefect/pull/1738)
- Expose `labels` kwarg in `flow.deploy` for convenient labeling of Flows - [#1742](https://github.com/PrefectHQ/prefect/pull/1742)

### Task Library

- None

### Fixes

- `FargateTaskEnvironment` now uses provided `family` for task definition naming - [#1713](https://github.com/PrefectHQ/prefect/pull/1713)
- Fix executor initialization missing `self` in `KubernetesJobEnvironment` - [#1713](https://github.com/PrefectHQ/prefect/pull/1713)
- Fix `identifier_label` not being generated on each run for Kubernetes based environments - [#1718](https://github.com/PrefectHQ/prefect/pull/1718)
- Fix issue where users could not override their user config path when deploying Docker to Cloud - [#1719](https://github.com/PrefectHQ/prefect/pull/1719)
- Respect order of inputs in merge - [#1736](https://github.com/~/1736)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Brett Naul](https://github.com/bnaul)

## 0.7.1 <Badge text="beta" type="success"/>

Released on Nov 5, 2019

### Features

- None

### Enhancements

- Add a `save`/`load` interface to Flows - [#1685](https://github.com/PrefectHQ/prefect/pull/1685), [#1695](https://github.com/PrefectHQ/prefect/pull/1695)
- Add option to specify `aws_session_token` for the `FargateTaskEnvironment` - [#1688](https://github.com/PrefectHQ/prefect/pull/1688)
- Add `EnvVarSecrets` for loading sensitive information from environment variables - [#1683](https://github.com/PrefectHQ/prefect/pull/1683)
- Add an informative version header to all Cloud client requests - [#1690](https://github.com/PrefectHQ/prefect/pull/1690)
- Auto-label Flow environments when using Local storage - [#1696](https://github.com/PrefectHQ/prefect/pull/1696)
- Batch upload logs to Cloud in a background thread for improved performance - [#1691](https://github.com/PrefectHQ/prefect/pull/1691)
- Include agent labels within each flow's configuration environment - [#1671](https://github.com/PrefectHQ/prefect/issues/1671)

### Task Library

- None

### Fixes

- Fix Fargate Agent access defaults and environment variable support - [#1687](https://github.com/PrefectHQ/prefect/pull/1687)
- Removed default python version for docker builds - [#1705](https://github.com/PrefectHQ/prefect/pull/1705)
- Attempt to install prefect in any docker image (if it is not already installed) - [#1704](https://github.com/PrefectHQ/prefect/pull/1704)
- Kubernetes Agent deployment yaml now respects new `prefecthq/prefect` image tagging convention - [#1707](https://github.com/PrefectHQ/prefect/pull/1707)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- None

## 0.7.0 To Affinity and Beyond <Badge text="beta" type="success"/>

Released October 29, 2019

### Features

- Flow Affinity: Environments and Agents now support labeling for execution specification - [#1651](https://github.com/PrefectHQ/prefect/pull/1651)
- Add new Secret Tasks for a pluggable and reusable Secrets API - [#1346](https://github.com/PrefectHQ/prefect/issues/1346), [#1587](https://github.com/PrefectHQ/prefect/issues/1587)

### Enhancements

- Add the ability to delete task tag limits using the client - [#1622](https://github.com/PrefectHQ/prefect/pull/1622)
- Adds an "Ask for help" button with a link to the prefect.io support page - [#1637](https://github.com/PrefectHQ/prefect/pull/1637)
- Reduces the size of the `prefecthq/prefect` Docker image by ~400MB, which is now the base Docker image used in Flows - [#1648](https://github.com/PrefectHQ/prefect/pull/1648)
- Add a new healthcheck for environment dependencies - [#1653](https://github.com/PrefectHQ/prefect/pull/1653)
- Add default 30 second timeout to Client requests - [#1672](https://github.com/PrefectHQ/prefect/pull/1672)

### Task Library

- Add new Secret Tasks for a pluggable and reusable Secrets API - [#1346](https://github.com/PrefectHQ/prefect/issues/1346), [#1587](https://github.com/PrefectHQ/prefect/issues/1587)
- Add support for directly passing credentials to task library tasks, instead of passing secret names - [#1667](https://github.com/PrefectHQ/prefect/pull/1673)

### Fixes

- Fix defaults for unspecified ARNs in the Fargate Agent - [#1634](https://github.com/PrefectHQ/prefect/pull/1634)
- Fix ShellTask return value on empty stdout - [#1632](https://github.com/PrefectHQ/prefect/pull/1632)
- Fix issue with some Cloud Secrets not being converted from strings - [#1655](https://github.com/PrefectHQ/prefect/pull/1655)
- Fix issue with Agent logging config setting not working - [#1657](https://github.com/PrefectHQ/prefect/pull/1657)
- Fix issue with SnowflakeQuery tasks not working - [#1663](https://github.com/PrefectHQ/prefect/pull/1663)

### Deprecations

- Tasks that accepted the name of a secret (often `credentials_secret`) will raise a deprecation warning - [#1667](https://github.com/PrefectHQ/prefect/pull/1673)

### Breaking Changes

- Fargate Agent now takes in all boto3 camel case arguments instead of specific snake case options - [#1649](https://github.com/PrefectHQ/prefect/pull/1649)
- `kubernetes` is no longer installed by default in deployed flow images - [#1653](https://github.com/PrefectHQ/prefect/pull/1653)
- Tasks that accepted the name of a secret (often `credentials_secret`) no longer have a default value for that argument, as it has been deprecated - [#1667](https://github.com/PrefectHQ/prefect/pull/1673)

### Contributors

- [Tobias Schmidt](https://github.com/royalts)

## 0.6.7 Oh Six Seven <Badge text="beta" type="success"/>

Released October 16, 2019

### Features

- Environments now allow for optional `on_start` and `on_exit` callbacks - [#1610](https://github.com/PrefectHQ/prefect/pull/1610)

### Enhancements

- Raise more informative error when calling `flow.visualize()` if Graphviz executable not installed - [#1602](https://github.com/PrefectHQ/prefect/pull/1602)
- Allow authentication to Azure Blob Storage with SAS token - [#1600](https://github.com/PrefectHQ/prefect/pull/1600)
- Additional debug logs to `Docker Container` and `Docker Image` tasks - [#920](https://github.com/PrefectHQ/prefect/issues/920)
- Changes to Fargate agent to support temporary credentials and IAM role based credentials within AWS compute such as a container or ec2 instance. [#1607](https://github.com/PrefectHQ/prefect/pull/1607)
- Local Secrets set through environment variable now retain their casing - [#1601](https://github.com/PrefectHQ/prefect/issues/1601)
- Agents can accept an optional `name` for logging and debugging - [#1612](https://github.com/PrefectHQ/prefect/pull/1612)
- Added AWS configuration options for Fargate Agent (task_role_arn, execution_role_arn) - [#1614](https://github.com/PrefectHQ/prefect/pull/1614)
- Change EmailTask to accept SMTP server settings as well as an email_from kwarg - [#1619](https://github.com/PrefectHQ/prefect/pull/1619)
- Add the ability to delete task tag limits using the client - [#1622](https://github.com/PrefectHQ/prefect/pull/1622)

### Task Library

- Add `return_all` kwarg to `ShellTask` for optionally returning all lines of stdout - [#1598](https://github.com/PrefectHQ/prefect/pull/1598)
- Add `CosmosDBCreateItem`, `CosmosDBReadItems`, `CosmosDBQueryItems` and for interacting with data stored on Azure Cosmos DB - [#1617](https://github.com/PrefectHQ/prefect/pull/1617)

### Fixes

- Fix issue with running local Flow without a schedule containing cached tasks - [#1599](https://github.com/PrefectHQ/prefect/pull/1599)
- Remove blank string for `task_run_id` in k8s resource manager - [#1604](https://github.com/PrefectHQ/prefect/pull/1604)
- Fix issue with merge task not working for pandas dataframes and numpy arrays - [#1609](https://github.com/PrefectHQ/prefect/pull/1609)

### Deprecations

- None

### Breaking Changes

- Local Secrets set through environment variable now retain their casing - [#1601](https://github.com/PrefectHQ/prefect/issues/1601)

### Contributors

- [Mark McDonald](https://github.com/mhmcdonal)
- [Sherman K](https://github.com/shrmnk)

## 0.6.6 Wait For It <Badge text="beta" type="success"/>

Released October 3, 2019

### Features

- Added `KubernetesJobEnvironment` - [#1548](https://github.com/PrefectHQ/prefect/pull/1548)
- Add ability to enforce Task concurrency limits by tag in Prefect Cloud - [#1570](https://github.com/PrefectHQ/prefect/pull/1570)
- Added `FargateTaskEnvironment` - [#1592](https://github.com/PrefectHQ/prefect/pull/1592)

### Enhancements

- Allow the `Client` to more gracefully handle failed login attempts on initialization - [#1535](https://github.com/PrefectHQ/prefect/pull/1535)
- Replace `DotDict` with `box.Box` - [#1518](https://github.com/PrefectHQ/prefect/pull/1518)
- Store `cached_inputs` on Failed states and call their result handlers if they were provided - [#1557](https://github.com/PrefectHQ/prefect/pull/1557)
- `raise_on_exception` no longer raises for Prefect Signals, as these are typically intentional / for control flow - [#1562](https://github.com/PrefectHQ/prefect/pull/1562)
- `run cloud` CLI command takes in optional `--parameters` as a file path pointing to a JSON file - [#1582](https://github.com/PrefectHQ/prefect/pull/1582)
- Always consider `Constant` tasks successful and unpack them immediately instead of submitting them for execution - [#1527](https://github.com/PrefectHQ/prefect/issues/1527)

### Task Library

- Add `BlobStorageDownload` and `BlobStorageUpload` for interacting with data stored on Azure Blob Storage - [#1538](https://github.com/PrefectHQ/prefect/pull/1538)
- Loosen Kubernetes Tasks' requirement of an API secret key - [#1559](https://github.com/PrefectHQ/prefect/pull/1559)
- Add tasks for working in Azure Machine Learning Serviec with Datastores and Datasets - [#1590](https://github.com/PrefectHQ/prefect/pull/1590)

### Fixes

- Fix issue with certain Pause / Resume / Retry pipelines retrying indefinitely - [#1177](https://github.com/PrefectHQ/prefect/issues/1177)
- Kubernetes Agent deployment YAML generation defaults to local Prefect version - [#1573](https://github.com/PrefectHQ/prefect/pull/1573)
- Fix issue with custom result handlers not working when called in `cached_inputs` - [#1585](https://github.com/PrefectHQ/prefect/pull/1585)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Fredrik Sannholm](https://github.com/frsann)

## 0.6.5 Agents of Environmental Change <Badge text="beta" type="success"/>

Released September 20, 2019

### Features

- Added Fargate agent - [#1521](https://github.com/PrefectHQ/prefect/pull/1521)
- Custom user-written environments can be deployed to Prefect Cloud - [#1534](https://github.com/PrefectHQ/prefect/pull/1534), [#1537](https://github.com/PrefectHQ/prefect/pull/1537)

### Enhancements

- Allow for Agents to correctly run in environments with differently calibrated clocks - [#1402](https://github.com/PrefectHQ/prefect/issues/1402)
- Refactor `RemoteEnvironment` to utilize the `get_flow` storage interface - [#1476](https://github.com/PrefectHQ/prefect/issues/1476)
- Ensure Task logger is available in context throughout every pipeline step of the run - [#1509](https://github.com/PrefectHQ/prefect/issues/1509)
- Skip Docker registry pushing and pulling on empty `registry_url` attribute - [#1525](https://github.com/PrefectHQ/prefect/pull/1525)
- Agents now log platform errors to flow runs which cannot deploy - [#1528](https://github.com/PrefectHQ/prefect/pull/1528)
- Updating `ShellTask` to work more like Airflow Bash Operator for streaming logs and returning values - [#1451](https://github.com/PrefectHQ/prefect/pull/1451)
- Agents now have a verbose/debug logging option for granular output - [#1532](https://github.com/PrefectHQ/prefect/pull/1532)
- `DaskKubernetesEnvironment` now allows for custom scheduler and worker specs - [#1543](https://github.com/PrefectHQ/prefect/pull/1534), [#1537](https://github.com/PrefectHQ/prefect/pull/1537)

### Task Library

- None

### Fixes

- Fix map error by removing `imagePullSecrets` from Kubernetes Agent install if not provided - [#1524](https://github.com/PrefectHQ/prefect/pull/1524)
- Fix issue with two INFO logs not being associated with the Task Run in Cloud - [#1526](https://github.com/PrefectHQ/prefect/pull/1526)
- `execute` CLI command can now load custom environments off of the flow object - [#1534](https://github.com/PrefectHQ/prefect/pull/1534)

### Deprecations

- None

### Breaking Changes

- Update `ShellTask` to return only the last line of stdout, as a string - [#1451](https://github.com/PrefectHQ/prefect/pull/1451)

### Contributors

- [Braun Reyes](https://github.com/braunreyes)

## 0.6.4 I installed Docker on a Windows machine and all I got was this release <Badge text="beta" type="success"/>

Released September 10, 2019

### Features

- Improve Windows compatibility for local development and deploying to Prefect Cloud - [#1441](https://github.com/PrefectHQ/prefect/pull/1441), [#1456](https://github.com/PrefectHQ/prefect/pull/1456), [#1465](https://github.com/PrefectHQ/prefect/pull/1465), [#1466](https://github.com/PrefectHQ/prefect/pull/1466)

### Enhancements

- Add OS platform check to Local Agent for running on Windows machines - [#1441](https://github.com/PrefectHQ/prefect/pull/1441)
- Add `--base-url` argument for Docker daemons to `agent start` CLI command - [#1441](https://github.com/PrefectHQ/prefect/pull/1441)
- Add environment labels for organizing / tagging different Flow execution environments - [#1438](https://github.com/PrefectHQ/prefect/issues/1438)
- Use `-U` option when installing `prefect` in Docker containers to override base image version - [#1461](https://github.com/PrefectHQ/prefect/pull/1461)
- Remove restriction that prevented `DotDict` classes from having keys that shadowed dict methods - [#1462](https://github.com/PrefectHQ/prefect/pull/1462)
- Added livenessProbe to Kubernetes Agent - [#1474](https://github.com/PrefectHQ/prefect/pull/1474)
- Ensure external Dask Clusters do not require Prefect Cloud environment variables to run Cloud flows - [#1481](https://github.com/PrefectHQ/prefect/pull/1481)

### Task Library

- None

### Fixes

- Fix incorrect import in `DaskKubernetesEnvironment` job template - [#1458](https://github.com/PrefectHQ/prefect/pull/1458)
- Raise error on Agents started without an appropriate API token - [#1459](https://github.com/PrefectHQ/prefect/pull/1459)
- Fix bug when calling `as_nested_dict` on `DotDicts` with an `items` key - [#1462](https://github.com/PrefectHQ/prefect/pull/1462)
- Fix `--resource-manager` flag on agent install invalidating `imagePullSecrets` - [#1469](https://github.com/PrefectHQ/prefect/pull/1469)
- Fix issue with user-written result handlers in Prefect Cloud preventing some states from being set - [#1480](https://github.com/PrefectHQ/prefect/pull/1480)

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- [Joe Schmid](https://github.com/joeschmid)
- [Brett Naul](https://github.com/bnaul)

## 0.6.3 Retry Release <Badge text="beta" type="success"/>

Released August 30, 2019

Maintenance release.

### Fixes

- Fix issue with reduced mapped tasks not respecting retries - [#1436](https://github.com/PrefectHQ/prefect/issues/1436)

## 0.6.2 Onboards and Upwards <Badge text="beta" type="success"/>

Released August 30, 2019

### Features

- Added Local, Kubernetes, and Nomad agents - [#1341](https://github.com/PrefectHQ/prefect/pull/1341)
- Add the ability for Tasks to sequentially loop - [#1356](https://github.com/PrefectHQ/prefect/pull/1356)

### Enhancements

- Adds a copy to clipboard button for codeblocks - [#213](https://github.com/prefecthq/prefect/issues/213)
- Updates Vuepress to v1.0.3 - [#770](https://github.com/prefecthq/prefect/issues/770)
- Introduce configurable default for storage class on Flows - [#1044](https://github.com/PrefectHQ/prefect/issues/1044)
- Allow for min and max workers to be specified in `DaskKubernetesEnvironment` - [#1338](https://github.com/PrefectHQ/prefect/pulls/1338)
- Use task and flow names for corresponding logger names for better organization - [#1355](https://github.com/PrefectHQ/prefect/pull/1355)
- `Paused` states subclass `Scheduled` and can have predefined expirations - [#1375](https://github.com/PrefectHQ/prefect/pull/1375)
- Introduce new Flow health checks prior to Cloud deployment - [#1372](https://github.com/PrefectHQ/prefect/issues/1372)
- Improve logging functionality to include tracebacks - [#1374](https://github.com/PrefectHQ/prefect/issues/1374)
- Improve CLI user experience while working with Cloud - [#1384](https://github.com/PrefectHQ/prefect/pull/1384/)
- Users can now create projects from the CLI - [#1388](https://github.com/PrefectHQ/prefect/pull/1388)
- Add a health check to confirm that serialized flows are valid prior to Cloud deploy - [#1397](https://github.com/PrefectHQ/prefect/pull/1397)
- Add `task_slug`, `flow_id`, and `flow_run_id` to context - [#1405](https://github.com/PrefectHQ/prefect/pull/1405)
- Support persistent `scheduled_start_time` for scheduled flow runs when run locally with `flow.run()` - [#1418](https://github.com/PrefectHQ/prefect/pull/1418), [#1429](https://github.com/PrefectHQ/prefect/pull/1429)
- Add `task_args` to `Task.map` - [#1390](https://github.com/PrefectHQ/prefect/issues/1390)
- Add auth flows for `USER`-scoped Cloud API tokens - [#1423](https://github.com/PrefectHQ/prefect/pull/1423)
- Add `AzureResultHandler` for handling results to / from Azure Blob storage containers - [#1421](https://github.com/PrefectHQ/prefect/pull/1421)
- Add new configurable `LocalDaskExecutor` - [#1336](https://github.com/PrefectHQ/prefect/issues/1336)
- Add CLI commands for working with Prefect Cloud auth - [#1431](https://github.com/PrefectHQ/prefect/pull/1431)

### Task Library

- Add new `SnowflakeQuery` task for using snowflake data warehouse - [#1113](https://github.com/PrefectHQ/prefect/issues/1113)

### Fixes

- Fix issue with Docker storage not respecting user-provided image names - [#1335](https://github.com/PrefectHQ/prefect/pull/1335)
- Fix issue with local retries in Cloud not always running in-process - [#1348](https://github.com/PrefectHQ/prefect/pull/1348)

### Deprecations

- Rename `SynchronousExecutor` as `LocalDaskExecutor` - [#1434](https://github.com/PrefectHQ/prefect/pull/1434)

### Breaking Changes

- Rename `CloudEnvironment` to `DaskKubernetesEnvironment` - [#1250](https://github.com/PrefectHQ/prefect/issues/1250)
- Remove unused `queue` method from all executors - [#1434](https://github.com/PrefectHQ/prefect/pull/1434)

### Contributors

- [Alex Kravetz](http://github.com/akravetz)

## 0.6.1 Prefect Timing <Badge text="beta" type="success"/>

Released August 8, 2019

### Features

- Introduce new `flows.checkpointing` configuration setting for checkpointing Tasks in local execution - [#1283](https://github.com/PrefectHQ/prefect/pull/1283)
- Introduce new, flexible `Schedule` objects - [#1320](https://github.com/PrefectHQ/prefect/pull/1320)

### Enhancements

- Allow passing of custom headers in `Client` calls - [#1255](https://github.com/PrefectHQ/prefect/pull/1255)
- Autogenerate informative names and tags for Docker images built for Flow storage - [#1237](https://github.com/PrefectHQ/prefect/issues/1237)
- Allow mixed-case configuration keys (environment variables are interpolated as lowercase) - [#1288](https://github.com/PrefectHQ/prefect/issues/1288)
- Ensure state handler errors are logged informatively - [#1326](https://github.com/PrefectHQ/prefect/issues/1326)

### Task Library

- Add `BigQueryLoadGoogleCloudStorage` task for loading data into BigQuery from Google Cloud Storage [#1317](https://github.com/PrefectHQ/prefect/pull/1317)

### Fixes

- Fix issue with logs not always arriving in long-standing Dask clusters - [#1244](https://github.com/PrefectHQ/prefect/pull/1244)
- Fix issue with `BuildImage` docker task not actually running to completion - [#1243](https://github.com/PrefectHQ/prefect/issues/1243)
- Fix `run --logs` CLI command not exiting on flow run finished state - [#1319](https://github.com/PrefectHQ/prefect/pull/1319)

### Deprecations

- `OneTimeSchedule` and `UnionSchedule` are deprecated, but remain callable as convenience functions - [#1320](https://github.com/PrefectHQ/prefect/pull/1320)
- Old-style schedules can be deserialized as new-style schedules, but support will eventually be dropped - [#1320](https://github.com/PrefectHQ/prefect/pull/1320)

### Breaking Changes

- `prefect.Client.graphql()` and `prefect.Client.post()` now use an explicit keyword, not `**kwargs`, for variables or parameters - [#1259](https://github.com/PrefectHQ/prefect/pull/1259)
- `auth add` CLI command replaced with `auth login` - [#1319](https://github.com/PrefectHQ/prefect/pull/1319)

### Contributors

- None

## 0.6.0 Cloud Ready <Badge text="beta" type="success"/>

Released July 16, 2019

### Features

- Add the Prefect CLI for working with core objects both locally and in cloud - [#1059](https://github.com/PrefectHQ/prefect/pull/1059)
- Add RemoteEnvironment for simple executor based executions - [#1215](https://github.com/PrefectHQ/prefect/pull/1215)
- Add the ability to share caches across Tasks and Flows - [#1222](https://github.com/PrefectHQ/prefect/pull/1222)
- Add the ability to submit tasks to specific dask workers for task / worker affinity - [#1229](https://github.com/PrefectHQ/prefect/pull/1229)

### Enhancements

- Refactor mapped caching to be independent of order - [#1082](https://github.com/PrefectHQ/prefect/issues/1082)
- Refactor caching to allow for caching across multiple runs - [#1082](https://github.com/PrefectHQ/prefect/issues/1082)
- Allow for custom secret names in Result Handlers - [#1098](https://github.com/PrefectHQ/prefect/issues/1098)
- Have `execute cloud-flow` CLI immediately set the flow run state to `Failed` if environment fails - [#1122](https://github.com/PrefectHQ/prefect/pull/1122)
- Validate configuration objects on initial load - [#1136](https://github.com/PrefectHQ/prefect/pull/1136)
- Add `auto_generated` property to Tasks for convenient filtering - [#1135](https://github.com/PrefectHQ/prefect/pull/1135)
- Disable dask work-stealing in Kubernetes via scheduler config - [#1166](https://github.com/PrefectHQ/prefect/pull/1166)
- Implement backoff retry settings on Client calls - [#1187](https://github.com/PrefectHQ/prefect/pull/1187)
- Explicitly set Dask keys for a better Dask visualization experience - [#1218](https://github.com/PrefectHQ/prefect/issues/1218)
- Implement a local cache which persists for the duration of a Python session - [#1221](https://github.com/PrefectHQ/prefect/issues/1221)
- Implement in-process retries for Cloud Tasks which request retry in less than one minute - [#1228](https://github.com/PrefectHQ/prefect/pull/1228)
- Support `Client.login()` with API tokens - [#1240](https://github.com/PrefectHQ/prefect/pull/1240)
- Add live log streaming for `prefect run cloud` command - [#1241](https://github.com/PrefectHQ/prefect/pull/1241)

### Task Library

- Add task to trigger AWS Step function workflow [#1012](https://github.com/PrefectHQ/prefect/issues/1012)
- Add task to copy files within Google Cloud Storage - [#1206](https://github.com/PrefectHQ/prefect/pull/1206)
- Add task for downloading files from Dropbox - [#1205](https://github.com/PrefectHQ/prefect/pull/1205)

### Fixes

- Fix issue with mapped caching in Prefect Cloud - [#1096](https://github.com/PrefectHQ/prefect/pull/1096)
- Fix issue with Result Handlers deserializing incorrectly in Cloud - [#1112](https://github.com/PrefectHQ/prefect/issues/1112)
- Fix issue caused by breaking change in `marshmallow==3.0.0rc7` - [#1151](https://github.com/PrefectHQ/prefect/pull/1151)
- Fix issue with passing results to Prefect signals - [#1163](https://github.com/PrefectHQ/prefect/issues/1163)
- Fix issue with `flow.update` not preserving mapped edges - [#1164](https://github.com/PrefectHQ/prefect/issues/1164)
- Fix issue with Parameters and Context not being raw dictionaries - [#1186](https://github.com/PrefectHQ/prefect/issues/1186)
- Fix issue with asynchronous, long-running mapped retries in Prefect Cloud - [#1208](https://github.com/PrefectHQ/prefect/pull/1208)
- Fix issue with automatically applied collections to task call arguments when using the imperative API - [#1211](https://github.com/PrefectHQ/prefect/issues/1211)

### Breaking Changes

- The CLI command `prefect execute-flow` and `prefect execute-cloud-flow` no longer exist - [#1059](https://github.com/PrefectHQ/prefect/pull/1059)
- The `slack_notifier` state handler now uses a `webhook_secret` kwarg to pull the URL from a Secret - [#1075](https://github.com/PrefectHQ/prefect/issues/1075)
- Use GraphQL for Cloud logging - [#1193](https://github.com/PrefectHQ/prefect/pull/1193)
- Remove the `CloudResultHandler` default result handler - [#1198](https://github.com/PrefectHQ/prefect/pull/1198)
- Rename `LocalStorage` to `Local` - [#1236](https://github.com/PrefectHQ/prefect/pull/1236)

### Contributors

- [Kwangyoun Jung](https://github.com/initialkommit)
- [Anes Benmerzoug](https://github.com/AnesBenmerzoug)

## 0.5.5 Season 8 <Badge text="beta" type="success"/>

Released May 31, 2019

Bugfix to address an unpinned dependency

## 0.5.4 A Release Has No Name <Badge text="beta" type="success"/>

Released May 28, 2019

### Features

- Add new `UnionSchedule` for combining multiple schedules, allowing for complex schedule specifications - [#428](https://github.com/PrefectHQ/prefect/issues/428)
- Allow for Cloud users to securely pull Docker images from private registries - [#1028](https://github.com/PrefectHQ/prefect/pull/1028)

### Enhancements

- Add `prefect_version` kwarg to `Docker` storage for controlling the version of prefect installed into your containers - [#1010](https://github.com/PrefectHQ/prefect/pull/1010), [#533](https://github.com/PrefectHQ/prefect/issues/533)
- Warn users if their Docker storage base image uses a different python version than their local machine - [#999](https://github.com/PrefectHQ/prefect/issues/999)
- Add flow run id to k8s labels on Cloud Environment jobs / pods for easier filtering in deployment - [#1016](https://github.com/PrefectHQ/prefect/pull/1016)
- Allow for `SlackTask` to pull the Slack webhook URL from a custom named Secret - [#1023](https://github.com/PrefectHQ/prefect/pull/1023)
- Raise informative errors when Docker storage push / pull fails - [#1029](https://github.com/PrefectHQ/prefect/issues/1029)
- Standardized `__repr__`s for various classes, to remove inconsistencies - [#617](https://github.com/PrefectHQ/prefect/issues/617)
- Allow for use of local images in Docker storage - [#1052](https://github.com/PrefectHQ/prefect/pull/1052)
- Allow for doc tests and doc generation to run without installing `all_extras` - [#1057](https://github.com/PrefectHQ/prefect/issues/1057)

### Task Library

- Add task for creating new branches in a GitHub repository - [#1011](https://github.com/PrefectHQ/prefect/pull/1011)
- Add tasks to create, delete, invoke, and list AWS Lambda functions [#1009](https://github.com/PrefectHQ/prefect/issues/1009)
- Add tasks for integration with spaCy pipelines [#1018](https://github.com/PrefectHQ/prefect/issues/1018)
- Add tasks for querying Postgres database [#1022](https://github.com/PrefectHQ/prefect/issues/1022)
- Add task for waiting on a Docker container to run and optionally raising for nonzero exit code - [#1061](https://github.com/PrefectHQ/prefect/pull/1061)
- Add tasks for communicating with Redis [#1021](https://github.com/PrefectHQ/prefect/issues/1021)

### Fixes

- Ensure that state change handlers are called even when unexpected initialization errors occur - [#1015](https://github.com/PrefectHQ/prefect/pull/1015)
- Fix an issue where a mypy assert relied on an unavailable import - [#1034](https://github.com/PrefectHQ/prefect/pull/1034)
- Fix an issue where user configurations were loaded after config interpolation had already taken place - [#1037](https://github.com/PrefectHQ/prefect/pull/1037)
- Fix an issue with saving a flow visualization to a file from a notebook - [#1056](https://github.com/PrefectHQ/prefect/pull/1056)
- Fix an issue in which mapped tasks incorrectly tried to run when their upstream was skipped - [#1068](https://github.com/PrefectHQ/prefect/issues/1068)
- Fix an issue in which mapped tasks were not using their caches locally - [#1067](https://github.com/PrefectHQ/prefect/issues/1067)

### Breaking Changes

- Changed the signature of `configuration.load_configuration()` - [#1037](https://github.com/PrefectHQ/prefect/pull/1037)
- Local Secrets now raise `ValueError`s when not found in context - [#1047](https://github.com/PrefectHQ/prefect/pull/1047)

### Contributors

- [Zach Angell](https://github.com/zangell44)
- [Nanda H Krishna](https://nandahkrishna.me)
- [Brett Naul](https://github.com/bnaul)
- [Jeremiah Lewis](https://github.com/jlewis91)
- [Dave Hirschfeld](https://github.com/dhirschfeld)

## 0.5.3 The Release is Bright and Full of Features <Badge text="beta" type="success"/>

Released May 7, 2019

### Features

- Add new `Storage` and `Environment` specifications - [#936](https://github.com/PrefectHQ/prefect/pull/936), [#956](https://github.com/PrefectHQ/prefect/pull/956)

### Enhancements

- Flow now has optional `storage` keyword - [#936](https://github.com/PrefectHQ/prefect/pull/936)
- Flow `environment` argument now defaults to a `CloudEnvironment` - [#936](https://github.com/PrefectHQ/prefect/pull/936)
- `Queued` states accept `start_time` arguments - [#955](https://github.com/PrefectHQ/prefect/pull/955)
- Add new `Bytes` and `Memory` storage classes for local testing - [#956](https://github.com/PrefectHQ/prefect/pull/956), [#961](https://github.com/PrefectHQ/prefect/pull/961)
- Add new `LocalEnvironment` execution environment for local testing - [#957](https://github.com/PrefectHQ/prefect/pull/957)
- Add new `Aborted` state for Flow runs which are cancelled by users - [#959](https://github.com/PrefectHQ/prefect/issues/959)
- Added an `execute-cloud-flow` CLI command for working with cloud deployed flows - [#971](https://github.com/PrefectHQ/prefect/pull/971)
- Add new `flows.run_on_schedule` configuration option for affecting the behavior of `flow.run` - [#972](https://github.com/PrefectHQ/prefect/issues/972)
- Allow for Tasks with `manual_only` triggers to be root tasks - [#667](https://github.com/PrefectHQ/prefect/issues/667)
- Allow compression of serialized flows [#993](https://github.com/PrefectHQ/prefect/pull/993)
- Allow for serialization of user written result handlers - [#623](https://github.com/PrefectHQ/prefect/issues/623)
- Allow for state to be serialized in certain triggers and cache validators - [#949](https://github.com/PrefectHQ/prefect/issues/949)
- Add new `filename` keyword to `flow.visualize` for automatically saving visualizations - [#1001](https://github.com/PrefectHQ/prefect/issues/1001)
- Add new `LocalStorage` option for storing Flows locally - [#1006](https://github.com/PrefectHQ/prefect/pull/1006)

### Task Library

- None

### Fixes

- Fix Docker storage not pulling correct flow path - [#968](https://github.com/PrefectHQ/prefect/pull/968)
- Fix `run_flow` loading to decode properly by use cloudpickle - [#978](https://github.com/PrefectHQ/prefect/pull/978)
- Fix Docker storage for handling flow names with spaces and weird characters - [#969](https://github.com/PrefectHQ/prefect/pull/969)
- Fix non-deterministic issue with mapping in the DaskExecutor - [#943](https://github.com/PrefectHQ/prefect/issues/943)

### Breaking Changes

- Remove `flow.id` and `task.id` attributes - [#940](https://github.com/PrefectHQ/prefect/pull/940)
- Removed old WIP environments - [#936](https://github.com/PrefectHQ/prefect/pull/936)
  (_Note_: Changes from [#936](https://github.com/PrefectHQ/prefect/pull/936) regarding environments don't break any Prefect code because environments weren't used yet outside of Cloud.)
- Update `flow.deploy` and `client.deploy` to use `set_schedule_active` kwarg to match Cloud - [#991](https://github.com/PrefectHQ/prefect/pull/991)
- Removed `Flow.generate_local_task_ids()` - [#992](#https://github.com/PrefectHQ/prefect/pull/992)

### Contributors

- None

## 0.5.2 Unredacted <Badge text="beta" type="success"/>

Released April 19, 2019

### Features

- Implement two new triggers that allow for specifying bounds on the number of failures or successes - [#933](https://github.com/PrefectHQ/prefect/issues/933)

### Enhancements

- `DaskExecutor(local_processes=True)` supports timeouts - [#886](https://github.com/PrefectHQ/prefect/issues/886)
- Calling `Secret.get()` from within a Flow context raises an informative error - [#927](https://github.com/PrefectHQ/prefect/issues/927)
- Add new keywords to `Task.set_upstream` and `Task.set_downstream` for handling keyed and mapped dependencies - [#823](https://github.com/PrefectHQ/prefect/issues/823)
- Downgrade default logging level to "INFO" from "DEBUG" - [#935](https://github.com/PrefectHQ/prefect/pull/935)
- Add start times to queued states - [#937](https://github.com/PrefectHQ/prefect/pull/937)
- Add `is_submitted` to states - [#944](https://github.com/PrefectHQ/prefect/pull/944)
- Introduce new `ClientFailed` state - [#938](https://github.com/PrefectHQ/prefect/issues/938)

### Task Library

- Add task for sending Slack notifications via Prefect Slack App - [#932](https://github.com/PrefectHQ/prefect/issues/932)

### Fixes

- Fix issue with timeouts behaving incorrectly with unpickleable objects - [#886](https://github.com/PrefectHQ/prefect/issues/886)
- Fix issue with Flow validation being performed even when eager validation was turned off - [#919](https://github.com/PrefectHQ/prefect/issues/919)
- Fix issue with downstream tasks with `all_failed` triggers running if an upstream Client call fails in Cloud - [#938](https://github.com/PrefectHQ/prefect/issues/938)

### Breaking Changes

- Remove `prefect make user config` from cli commands - [#904](https://github.com/PrefectHQ/prefect/issues/904)
- Change `set_schedule_active` keyword in Flow deployments to `set_schedule_inactive` to match Cloud - [#941](https://github.com/PrefectHQ/prefect/pull/941)

### Contributors

- None

## 0.5.1 It Takes a Village <Badge text="beta" type="success"/>

Released April 4, 2019

### Features

- API reference documentation is now versioned - [#270](https://github.com/PrefectHQ/prefect/issues/270)
- Add `S3ResultHandler` for handling results to / from S3 buckets - [#879](https://github.com/PrefectHQ/prefect/pull/879)
- Add ability to use `Cached` states across flow runs in Cloud - [#885](https://github.com/PrefectHQ/prefect/pull/885)

### Enhancements

- Bump to latest version of `pytest` (4.3) - [#814](https://github.com/PrefectHQ/prefect/issues/814)
- `Client.deploy` accepts optional `build` kwarg for avoiding building Flow environment - [#876](https://github.com/PrefectHQ/prefect/pull/876)
- Bump `distributed` to 1.26.1 for enhanced security features - [#878](https://github.com/PrefectHQ/prefect/pull/878)
- Local secrets automatically attempt to load secrets as JSON - [#883](https://github.com/PrefectHQ/prefect/pull/883)
- Add task logger to context for easily creating custom logs during task runs - [#884](https://github.com/PrefectHQ/prefect/issues/884)

### Task Library

- Add `ParseRSSFeed` for parsing a remote RSS feed - [#856](https://github.com/PrefectHQ/prefect/pull/856)
- Add tasks for working with Docker containers and imaged - [#864](https://github.com/PrefectHQ/prefect/pull/864)
- Add task for creating a BigQuery table - [#895](https://github.com/PrefectHQ/prefect/pull/895)

### Fixes

- Only checkpoint tasks if running in cloud - [#839](https://github.com/PrefectHQ/prefect/pull/839), [#854](https://github.com/PrefectHQ/prefect/pull/854)
- Adjusted small flake8 issues for names, imports, and comparisons - [#849](https://github.com/PrefectHQ/prefect/pull/849)
- Fix bug preventing `flow.run` from properly using cached tasks - [#861](https://github.com/PrefectHQ/prefect/pull/861)
- Fix tempfile usage in `flow.visualize` so that it runs on Windows machines - [#858](https://github.com/PrefectHQ/prefect/issues/858)
- Fix issue caused by Python 3.5.2 bug for Python 3.5.2 compatibility - [#857](https://github.com/PrefectHQ/prefect/issues/857)
- Fix issue in which `GCSResultHandler` was not pickleable - [#879](https://github.com/PrefectHQ/prefect/pull/879)
- Fix issue with automatically converting callables and dicts to tasks - [#894](https://github.com/PrefectHQ/prefect/issues/894)

### Breaking Changes

- Change the call signature of `Dict` task from `run(**task_results)` to `run(keys, values)` - [#894](https://github.com/PrefectHQ/prefect/issues/894)

### Contributors

- [ColCarroll](https://github.com/ColCarroll)
- [dhirschfeld](https://github.com/dhirschfeld)
- [BasPH](https://github.com/BasPH)
- [Miloš Garunović](https://github.com/milosgarunovic)
- [Nash Taylor](https://github.com/ntaylorwss)

## 0.5.0 Open Source Launch! <Badge text="beta" type="success"/>

Released March 24, 2019

### Features

- Add `checkpoint` option for individual `Task`s, as well as a global `checkpoint` config setting for storing the results of Tasks using their result handlers - [#649](https://github.com/PrefectHQ/prefect/pull/649)
- Add `defaults_from_attrs` decorator to easily construct `Task`s whose attributes serve as defaults for `Task.run` - [#293](https://github.com/PrefectHQ/prefect/issues/293)
- Environments follow new hierarchy (PIN-3) - [#670](https://github.com/PrefectHQ/prefect/pull/670)
- Add `OneTimeSchedule` for one-time execution at a specified time - [#680](https://github.com/PrefectHQ/prefect/pull/680)
- `flow.run` is now a blocking call which will run the Flow, on its schedule, and execute full state-based execution (including retries) - [#690](https://github.com/PrefectHQ/prefect/issues/690)
- Pre-populate `prefect.context` with various formatted date strings during execution - [#704](https://github.com/PrefectHQ/prefect/pull/704)
- Add ability to overwrite task attributes such as "name" when calling tasks in the functional API - [#717](https://github.com/PrefectHQ/prefect/issues/717)
- Release Prefect Core under the Apache 2.0 license - [#762](https://github.com/PrefectHQ/prefect/pull/762)

### Enhancements

- Refactor all `State` objects to store fully hydrated `Result` objects which track information about how results should be handled - [#612](https://github.com/PrefectHQ/prefect/pull/612), [#616](https://github.com/PrefectHQ/prefect/pull/616)
- Add `google.cloud.storage` as an optional extra requirement so that the `GCSResultHandler` can be exposed better - [#626](https://github.com/PrefectHQ/prefect/pull/626)
- Add a `start_time` check for Scheduled flow runs, similar to the one for Task runs - [#605](https://github.com/PrefectHQ/prefect/issues/605)
- Project names can now be specified for deployments instead of IDs - [#633](https://github.com/PrefectHQ/prefect/pull/633)
- Add a `createProject` mutation function to the client - [#633](https://github.com/PrefectHQ/prefect/pull/633)
- Add timestamp to auto-generated API docs footer - [#639](https://github.com/PrefectHQ/prefect/pull/639)
- Refactor `Result` interface into `Result` and `SafeResult` - [#649](https://github.com/PrefectHQ/prefect/pull/649)
- The `manual_only` trigger will pass if `resume=True` is found in context, which indicates that a `Resume` state was passed - [#664](https://github.com/PrefectHQ/prefect/issues/664)
- Added DockerOnKubernetes environment (PIN-3) - [#670](https://github.com/PrefectHQ/prefect/pull/670)
- Added Prefect docker image (PIN-3) - [#670](https://github.com/PrefectHQ/prefect/pull/670)
- `defaults_from_attrs` now accepts a splatted list of arguments - [#676](https://github.com/PrefectHQ/prefect/issues/676)
- Add retry functionality to `flow.run(on_schedule=True)` for local execution - [#680](https://github.com/PrefectHQ/prefect/pull/680)
- Add `helper_fns` keyword to `ShellTask` for pre-populating helper functions to commands - [#681](https://github.com/PrefectHQ/prefect/pull/681)
- Convert a few DEBUG level logs to INFO level logs - [#682](https://github.com/PrefectHQ/prefect/issues/682)
- Added DaskOnKubernetes environment (PIN-3) - [#695](https://github.com/PrefectHQ/prefect/pull/695)
- Load `context` from Cloud when running flows - [#699](https://github.com/PrefectHQ/prefect/pull/699)
- Add `Queued` state - [#705](https://github.com/PrefectHQ/prefect/issues/705)
- `flow.serialize()` will always serialize its environment, regardless of `build` - [#696](https://github.com/PrefectHQ/prefect/issues/696)
- `flow.deploy()` now raises an informative error if your container cannot deserialize the Flow - [#711](https://github.com/PrefectHQ/prefect/issues/711)
- Add `_MetaState` as a parent class for states that modify other states - [#726](https://github.com/PrefectHQ/prefect/pull/726)
- Add `flow` keyword argument to `Task.set_upstream()` and `Task.set_downstream()` - [#749](https://github.com/PrefectHQ/prefect/pull/749)
- Add `is_retrying()` helper method to all `State` objects - [#753](https://github.com/PrefectHQ/prefect/pull/753)
- Allow for state handlers which return `None` - [#753](https://github.com/PrefectHQ/prefect/pull/753)
- Add daylight saving time support for `CronSchedule` - [#729](https://github.com/PrefectHQ/prefect/pull/729)
- Add `idempotency_key` and `context` arguments to `Client.create_flow_run` - [#757](https://github.com/PrefectHQ/prefect/issues/757)
- Make `EmailTask` more secure by pulling credentials from secrets - [#706](https://github.com/PrefectHQ/prefect/issues/706)

### Task Library

- Add `GCSUpload` and `GCSDownload` for uploading / retrieving string data to / from Google Cloud Storage - [#673](https://github.com/PrefectHQ/prefect/pull/673)
- Add `BigQueryTask` and `BigQueryInsertTask` for executing queries against BigQuery tables and inserting data - [#678](https://github.com/PrefectHQ/prefect/pull/678), [#685](https://github.com/PrefectHQ/prefect/pull/685)
- Add `FilterTask` for filtering out lists of results - [#637](https://github.com/PrefectHQ/prefect/issues/637)
- Add `S3Download` and `S3Upload` for interacting with data stored on AWS S3 - [#692](https://github.com/PrefectHQ/prefect/issues/692)
- Add `AirflowTask` and `AirflowTriggerDAG` tasks to the task library for running individual Airflow tasks / DAGs - [#735](https://github.com/PrefectHQ/prefect/issues/735)
- Add `OpenGitHubIssue` and `CreateGitHubPR` tasks for interacting with GitHub repositories - [#771](https://github.com/PrefectHQ/prefect/pull/771)
- Add Kubernetes tasks for deployments, jobs, pods, and services - [#779](https://github.com/PrefectHQ/prefect/pull/779)
- Add Airtable tasks - [#803](https://github.com/PrefectHQ/prefect/pull/803)
- Add Twitter tasks - [#803](https://github.com/PrefectHQ/prefect/pull/803)
- Add `GetRepoInfo` for pulling GitHub repository information - [#816](https://github.com/PrefectHQ/prefect/pull/816)

### Fixes

- Fix edge case in doc generation in which some `Exception`s' call signature could not be inspected - [#513](https://github.com/PrefectHQ/prefect/issues/513)
- Fix bug in which exceptions raised within flow runner state handlers could not be sent to Cloud - [#628](https://github.com/PrefectHQ/prefect/pull/628)
- Fix issue wherein heartbeats were not being called on a fixed interval - [#669](https://github.com/PrefectHQ/prefect/pull/669)
- Fix issue wherein code blocks inside of method docs couldn't use `**kwargs` - [#658](https://github.com/PrefectHQ/prefect/issues/658)
- Fix bug in which Prefect-generated Keys for S3 buckets were not properly converted to strings - [#698](https://github.com/PrefectHQ/prefect/pull/698)
- Fix next line after Docker Environment push/pull from overwriting progress bar - [#702](https://github.com/PrefectHQ/prefect/pull/702)
- Fix issue with `JinjaTemplate` not being pickleable - [#710](https://github.com/PrefectHQ/prefect/pull/710)
- Fix issue with creating secrets from JSON documents using the Core Client - [#715](https://github.com/PrefectHQ/prefect/pull/715)
- Fix issue with deserialization of JSON secrets unnecessarily calling `json.loads` - [#716](https://github.com/PrefectHQ/prefect/pull/716)
- Fix issue where `IntervalSchedules` didn't respect daylight saving time after serialization - [#729](https://github.com/PrefectHQ/prefect/pull/729)

### Breaking Changes

- Remove the `BokehRunner` and associated webapp - [#609](https://github.com/PrefectHQ/prefect/issues/609)
- Rename `ResultHandler` methods from `serialize` / `deserialize` to `write` / `read` - [#612](https://github.com/PrefectHQ/prefect/pull/612)
- Refactor all `State` objects to store fully hydrated `Result` objects which track information about how results should be handled - [#612](https://github.com/PrefectHQ/prefect/pull/612), [#616](https://github.com/PrefectHQ/prefect/pull/616)
- `Client.create_flow_run` now returns a string instead of a `GraphQLResult` object to match the API of `deploy` - [#630](https://github.com/PrefectHQ/prefect/pull/630)
- `flow.deploy` and `client.deploy` require a `project_name` instead of an ID - [#633](https://github.com/PrefectHQ/prefect/pull/633)
- Upstream state results now take precedence for task inputs over `cached_inputs` - [#591](https://github.com/PrefectHQ/prefect/issues/591)
- Rename `Match` task (used inside control flow) to `CompareValue` - [#638](https://github.com/PrefectHQ/prefect/pull/638)
- `Client.graphql()` now returns a response with up to two keys (`data` and `errors`). Previously the `data` key was automatically selected - [#642](https://github.com/PrefectHQ/prefect/pull/642)
- `ContainerEnvironment` was changed to `DockerEnvironment` - [#670](https://github.com/PrefectHQ/prefect/pull/670)
- The environment `from_file` was moved to `utilities.environments` - [#670](https://github.com/PrefectHQ/prefect/pull/670)
- Removed `start_tasks` argument from `FlowRunner.run()` and `check_upstream` argument from `TaskRunner.run()` - [#672](https://github.com/PrefectHQ/prefect/pull/672)
- Remove support for Python 3.4 - [#671](https://github.com/PrefectHQ/prefect/issues/671)
- `flow.run` is now a blocking call which will run the Flow, on its schedule, and execute full state-based execution (including retries) - [#690](https://github.com/PrefectHQ/prefect/issues/690)
- Remove `make_return_failed_handler` as `flow.run` now returns all task states - [#693](https://github.com/PrefectHQ/prefect/pull/693)
- Refactor Airflow migration tools into a single `AirflowTask` in the task library for running individual Airflow tasks - [#735](https://github.com/PrefectHQ/prefect/issues/735)
- `name` is now required on all Flow objects - [#732](https://github.com/PrefectHQ/prefect/pull/732)
- Separate installation "extras" packages into multiple, smaller extras - [#739](https://github.com/PrefectHQ/prefect/issues/739)
- `Flow.parameters()` always returns a set of parameters - [#756](https://github.com/PrefectHQ/prefect/pull/756)

## 0.4.1 <Badge text="beta" type="success"/>

Released January 31, 2019

### Features

- Add ability to run scheduled flows locally via `on_schedule` kwarg in `flow.run()` - [#519](https://github.com/PrefectHQ/prefect/issues/519)
- Allow tasks to specify their own result handlers, ensure inputs and outputs are stored only when necessary, and ensure no raw data is sent to the database - [#587](https://github.com/PrefectHQ/prefect/pull/587)

### Enhancements

- Allow for building `ContainerEnvironment`s locally without pushing to registry - [#514](https://github.com/PrefectHQ/prefect/issues/514)
- Make mapping more robust when running children tasks multiple times - [#541](https://github.com/PrefectHQ/prefect/pull/541)
- Always prefer `cached_inputs` over upstream states, if available - [#546](https://github.com/PrefectHQ/prefect/pull/546)
- Add hooks to `FlowRunner.initialize_run()` for manipulating task states and contexts - [#548](https://github.com/PrefectHQ/prefect/pull/548)
- Improve state-loading strategy for Prefect Cloud - [#555](https://github.com/PrefectHQ/prefect/issues/555)
- Introduce `on_failure` kwarg to Tasks and Flows for user-friendly failure callbacks - [#551](https://github.com/PrefectHQ/prefect/issues/551)
- Include `scheduled_start_time` in context for Flow runs - [#524](https://github.com/PrefectHQ/prefect/issues/524)
- Add GitHub PR template - [#542](https://github.com/PrefectHQ/prefect/pull/542)
- Allow flows to be deployed to Prefect Cloud without a project id - [#571](https://github.com/PrefectHQ/prefect/pull/571)
- Introduce serialization schemas for ResultHandlers - [#572](https://github.com/PrefectHQ/prefect/issues/572)
- Add new `metadata` attribute to States for managing user-generated results - [#573](https://github.com/PrefectHQ/prefect/issues/573)
- Add new 'JSONResultHandler' for serializing small bits of data without external storage - [#576](https://github.com/PrefectHQ/prefect/issues/576)
- Use `JSONResultHandler` for all Parameter caching - [#590](https://github.com/PrefectHQ/prefect/pull/590)

### Fixes

- Fixed `flow.deploy()` attempting to access a nonexistent string attribute - [#503](https://github.com/PrefectHQ/prefect/pull/503)
- Ensure all logs make it to the logger service in deployment - [#508](https://github.com/PrefectHQ/prefect/issues/508), [#552](https://github.com/PrefectHQ/prefect/issues/552)
- Fix a situation where `Paused` tasks would be treated as `Pending` and run - [#535](https://github.com/PrefectHQ/prefect/pull/535)
- Ensure errors raised in state handlers are trapped appropriately in Cloud Runners - [#554](https://github.com/PrefectHQ/prefect/pull/554)
- Ensure unexpected errors raised in FlowRunners are robustly handled - [#568](https://github.com/PrefectHQ/prefect/pull/568)
- Fixed non-deterministic errors in mapping caused by clients resolving futures of other clients - [#569](https://github.com/PrefectHQ/prefect/pull/569)
- Older versions of Prefect will now ignore fields added by newer versions when deserializing objects - [#583](https://github.com/PrefectHQ/prefect/pull/583)
- Result handler failures now result in clear task run failures - [#575](https://github.com/PrefectHQ/prefect/issues/575)
- Fix issue deserializing old states with empty metadata - [#590](https://github.com/PrefectHQ/prefect/pull/590)
- Fix issue serializing `cached_inputs` - [#594](https://github.com/PrefectHQ/prefect/pull/594)

### Breaking Changes

- Move `prefect.client.result_handlers` to `prefect.engine.result_handlers` - [#512](https://github.com/PrefectHQ/prefect/pull/512)
- Removed `inputs` kwarg from `TaskRunner.run()` - [#546](https://github.com/PrefectHQ/prefect/pull/546)
- Moves the `start_task_ids` argument from `FlowRunner.run()` to `Environment.run()` - [#544](https://github.com/PrefectHQ/prefect/issues/544), [#545](https://github.com/PrefectHQ/prefect/pull/545)
- Convert `timeout` kwarg from `timedelta` to `integer` - [#540](https://github.com/PrefectHQ/prefect/issues/540)
- Remove `timeout` kwarg from `executor.wait` - [#569](https://github.com/PrefectHQ/prefect/pull/569)
- Serialization of States will _ignore_ any result data that hasn't been processed - [#581](https://github.com/PrefectHQ/prefect/pull/581)
- Removes `VersionedSchema` in favor of implicit versioning: serializers will ignore unknown fields and the `create_object` method is responsible for recreating missing ones - [#583](https://github.com/PrefectHQ/prefect/pull/583)
- Convert and rename `CachedState` to a successful state named `Cached`, and also remove the superfluous `cached_result` attribute - [#586](https://github.com/PrefectHQ/prefect/issues/586)

## 0.4.0 <Badge text="beta" type="success"/>

Released January 8, 2019

### Features

- Add support for Prefect Cloud - [#374](https://github.com/PrefectHQ/prefect/pull/374), [#406](https://github.com/PrefectHQ/prefect/pull/406), [#473](https://github.com/PrefectHQ/prefect/pull/473), [#491](https://github.com/PrefectHQ/prefect/pull/491)
- Add versioned serialization schemas for `Flow`, `Task`, `Parameter`, `Edge`, `State`, `Schedule`, and `Environment` objects - [#310](https://github.com/PrefectHQ/prefect/pull/310), [#318](https://github.com/PrefectHQ/prefect/pull/318), [#319](https://github.com/PrefectHQ/prefect/pull/319), [#340](https://github.com/PrefectHQ/prefect/pull/340)
- Add ability to provide `ResultHandler`s for storing private result data - [#391](https://github.com/PrefectHQ/prefect/pull/391), [#394](https://github.com/PrefectHQ/prefect/pull/394), [#430](https://github.com/PrefectHQ/prefect/pull/430/)
- Support depth-first execution of mapped tasks and tracking of both the static "parent" and dynamic "children" via `Mapped` states - [#485](https://github.com/PrefectHQ/prefect/pull/485)

### Enhancements

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

### Features

- Refactor `FlowRunner` and `TaskRunner` into a modular `Runner` pipelines - [#260](https://github.com/PrefectHQ/prefect/pull/260), [#267](https://github.com/PrefectHQ/prefect/pull/267)
- Add configurable `state_handlers` for `FlowRunners`, `Flows`, `TaskRunners`, and `Tasks` - [#264](https://github.com/PrefectHQ/prefect/pull/264), [#267](https://github.com/PrefectHQ/prefect/pull/267)
- Add gmail and slack notification state handlers w/ tutorial - [#274](https://github.com/PrefectHQ/prefect/pull/274), [#294](https://github.com/PrefectHQ/prefect/pull/294)

### Enhancements

- Add a new method `flow.get_tasks()` for easily filtering flow tasks by attribute - [#242](https://github.com/PrefectHQ/prefect/pull/242)
- Add new `JinjaTemplate` for easily rendering jinja templates - [#200](https://github.com/PrefectHQ/prefect/issues/200)
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

### Features

- Local parallelism with `DaskExecutor` - [#151](https://github.com/PrefectHQ/prefect/issues/151), [#186](https://github.com/PrefectHQ/prefect/issues/186)
- Resource throttling based on `tags` - [#158](https://github.com/PrefectHQ/prefect/issues/158), [#186](https://github.com/PrefectHQ/prefect/issues/186)
- `Task.map` for mapping tasks - [#186](https://github.com/PrefectHQ/prefect/issues/186)
- Added `AirFlow` utility for importing Airflow DAGs as Prefect Flows - [#232](https://github.com/PrefectHQ/prefect/pull/232)

### Enhancements

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

### Features

- Support for user configuration files - [#195](https://github.com/PrefectHQ/prefect/pull/195)

### Enhancements

- None

### Fixes

- Let DotDicts accept non-string keys - [#193](https://github.com/PrefectHQ/prefect/pull/193), [#194](https://github.com/PrefectHQ/prefect/pull/194)

### Breaking Changes

- None

## 0.3.0 <Badge text="alpha" type="warn"/>

Released August 20, 2018

### Features

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

### Enhancements

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
