---
description: Define rules and policies for flow runs and task runs.
tags:
    - environment variables
    - settings
    - configuration
    - task runs
    - concurrency
---

# Settings

A key tenet around which we built Prefect is the ability to govern of flow and task state transitions through policies and rules. Prefect provides a robust set of environment variables and settings that enable you to define the execution environment, policies, and rules needed to orchestrate your workflows successfully.

Prefect's settings are documented under [prefect.utilities.settings[prefect.utilities.settings] and type-validated, ensuring that configuration is a first-class experience.  

From Python, settings can be accessed by examining `prefect.settings`, and users can view their Orion server's current settings from its UI.

## Environment Variables
All settings can be modified via environment variables using the following syntax:
```
[PREFIX]_[SETTING]=value
```

- The `PREFIX` is a string that describes the fully-qualified name of the setting. All prefixes begin with `PREFECT_` and add additional words only to describe nested settings. For example, the prefix for `prefect.settings.home` is just `PREFECT_`, because it is a top-level key in the `settings` object. The prefix for `prefect.settings.orion.api.port` is `PREFECT_ORION_API_`, indicating its nested position.
- The `SETTING` corresponds directly to the name of the prefect setting's key. Note that while keys are lowercase, we provide environment variables as uppercase by convention. 

### Examples
A top-level setting:
```shell
# environment variable
PREFECT_HOME="/path/to/home"
```
```python
# python
prefect.settings.home # PosixPath('/path/to/home')
```

A nested setting:

```shell
# environment variable
PREFECT_ORION_API_PORT=4242
```
```python
# python
prefect.settings.orion.api.port # 4242
```

## Task run concurrency limits

There are situations in which you want to actively prevent too many tasks from running simultaneously. For example, if many tasks across multiple flows are designed to interact with a database that only allows 10 connections, you want to make sure that no more than 10 tasks that connect to this database are running at any given time.

Prefect has built-in functionality for achieving this: task concurrency limits.

Task concurrency limits use [task tags](/concepts/tasks.md#tags). You can specify an optional concurrency limit as the maximum number of concurrent task runs in a `Running` state for tasks with a given tag. The specified concurrency limit applies to any task to which the tag is applied.

If a task has multiple tags, it will run only if _all_ tags have available concurrency. 

Tags without explicit limits are considered to have unlimited concurrency.

!!! note 0 concurrency limit aborts task runs 

    Currently, if the concurrency limit is set to 0 for a tag, any attempt to run a task with that tag will be aborted instead of delayed.

### Execution behavior

Task tag limits are checked whenever a task run attempts to enter a [`Running` state](/concepts/states.md). 

If there are no concurrency slots available for any one of your task's tags, the transition to a `Running` state will be delayed and the client is instructed to try entering a `Running` state again in 30 seconds. 

!!! warning Concurrency limits in subflows

    Using concurrency limits on task runs in subflows can cause deadlocks. As a best practice, configure your tags and concurrency limits to avoid setting limits on task runs in subflows.

### Configuring concurrency limits

You can set concurrency limits on as few or as many tags as you wish. You can set limits through the CLI or via API by using the `OrionClient`.

#### CLI

You can create, list, and remove concurrency limits by using Prefect CLI `concurrency-limit` commands.

```bash
$ prefect concurrency_limit [command] [arguments]
```

| Command | Description |
| --- | --- |
| create | Create a concurrency limit by specifying a tag and limit. |
| delete | Delete the concurrency limit set on the specified tag. |
| ls     | View all defined concurrency limits. |
| read   | View details about a concurrency limit. `active_slots` shows a list of IDs for task runs that are currently using a concurrency slot. |

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```bash
$ prefect concurrency_limit create small_instance 10
```

To delete the concurrency limit on the 'small_instance' tag:

```bash
$ prefect concurrency_limit delete small_instance
```

#### Python client

To update your tag concurrency limits programmatically, use [`OrionClient.create_concurrency_limit`](/api-ref/prefect/client/#prefect.client.OrionClient.create_concurrency_limit). 

`create_concurrency_limit` takes two arguments:

- `tag` specifies the task tag on which you're setting a limit.
- `concurrency_limit` specifies the maximum number of concurrent task runs for that tag.

For example, to set a concurrency limit of 10 on the 'small_instance' tag:

```python
from prefect.client import OrionClient

with OrionClient as client:
    # set a concurrency limit of 10 on the 'small_instance' tag
    limit_id = client.create_concurrency_limit(tag="small_instance", concurrency_limit=10)
```

To remove all concurrency limits on a tag, use [`OrionClient.delete_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.OrionClient.delete_concurrency_limit_by_tag), passing the tag:

```python
with OrionClient as client:
    # remove a concurrency limit on the 'small_instance' tag
    client.delete_concurrency_limit_by_tag(tag="small_instance")
```

If you wish to query for the currently set limit on a tag, use [`OrionClient.read_concurrency_limit_by_tag`](/api-ref/prefect/client/#prefect.client.OrionClient.read_concurrency_limit_by_tag), passing the tag:

To see _all_ of your limits across all of your tags, use [`OrionClient.read_concurrency_limits`](/api-ref/prefect/client/#prefect.client.OrionClient.read_concurrency_limits).

```python
with OrionClient as client:
    # query the concurrency limit on the 'small_instance' tag
    limit = client.read_concurrency_limit_by_tag(tag="small_instance")
```
