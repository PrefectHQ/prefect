# Changelog

## Unreleased <Badge text="beta" type="success"/>

These changes are available in the [master branch](https://github.com/PrefectHQ/prefect).

### Features

- None

### Enhancements

- Add a `save`/`load` interface to Flows - [#1685](https://github.com/PrefectHQ/prefect/pull/1685)

### Task Library

- None

### Deprecations

- None

### Breaking Changes

- None

### Contributors

- None

## 0.7.0 To Affinity and Beyond <Badge text="beta" type="success">

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
