# Flows

Flows can be registered with the Prefect API for scheduling and execution, as well as management of run histories, logs, and other important metrics.

## Registration

### CLI

To register a flow (or flows) with the `prefect` cli, you can use the [prefect
register](/api/latest/cli/register.md#register) command.

```bash
$ prefect register --project "my project" --path myflow.py
```

By default this will register all flows found in `myflow.py`. If you want to
select a specific flow, you can use the `--name` flag:

```bash
$ prefect register --project "my project" --path myflow.py --name "my flow's name"
```

The CLI command supports several additional options, see the
[docs](/api/latest/cli/register.md#register) for more information.


!!! tip Get started quickly
    Prefect provides a classic Hello World flow to get you started. Just register the flow included in the Prefect Python package.
    ```bash
    $ prefect register --project "my project" --module "prefect.hello_world"
    ```


### Core Client

To register a flow from Prefect Core, use its `register()` method:

```python
flow.register(project_name="my project")
```

!!! warning Projects
    Registering a flow with the backend API requires it to be registered to a project. To create a project see [the "creating a project" tutorial](projects.html#creating-a-project).


!!! tip Deduplicating registration calls
    Each call to `flow.register()` will bump the version of the flow in the
    backend.  If you are registering flows using automation, you may want to pass
    an `idempotency_key` which will only create a new version when the key changes.
    For example, we can take advantage of the hash of the serialized flow to only
    register a new version of the flow when it has changed:

    ```python
    flow.register(
        project_name="Hello, World!",
        idempotency_key=flow.serialized_hash()
    )
    ```



Note that this assumes that if you are using Prefect Cloud that you have already [authenticated](/orchestration/getting-started/set-up.html#authenticate-with-prefect-cloud). For more information on Flow registration see [here](/orchestration/getting-started/registering-and-running-a-flow.html#register-a-flow).

### GraphQL <Badge text="GQL"/>

To register a flow via the GraphQL API, first serialize the `Flow` object to JSON:

```python
flow.serialize()
```

Next, use the `create_flow` GraphQL mutation to pass the serialized `Flow` to the Prefect API. You will also need to provide a project ID:

```graphql
mutation($flow: JSON!) {
  create_flow(input: { serialized_flow: $flow, project_id: "<project id>" }) {
    id
  }
}
```

```json
// graphql variables
{
    serialized_flow: <the serialized flow JSON>
}
```

## Versioning

Every registered flow is part of a version group and has a version group id and a flow group id. 

The version group id can be provided when [registering a flow](/api/latest/core/flow.html#flow-2). If no version group id is provided at registration, the platform checks if any other flows in the same project have the same name as the new flow. If so, the new flow is assigned to the same version group as the other flow.  Version group ids can be used when creating a flow run and, if provided, the unique unarchived version in this version group will be run; this input is useful as a stable API for running a regularly updated flow.

The flow group id is a UUID and is not currently editable.  The flow group id can be used when setting [flow group settings](/orchestration/ui/flow.html#flow-group-settings) such as default parameters and labels.

Each version group can only have one active flow at a time. When a new flow is added to a version group, any other flows are automatically archived. Archiving maintains their history and data, but prevents them from being run.

### UI

All versions of a flow can be viewed [directly in the UI](/orchestration/ui/flow.md#versions). If you are using Prefect Cloud then version groups can be managed from the [team settings page](/orchestration/ui/team-settings).

![](/orchestration/ui/flow-versions.png)

### GraphQL <Badge text="GQL"/>

You can control how the API versions your flows by providing a `version_group_id` whenever you register a flow (exposed via the `version_group_id` keyword argument in `flow.register`). Flows which provide the same `version_group_id` will be considered versions of each other. By default, flows with the same name in the same Project will be given the same `version_group_id` and are considered "versions" of each other. Anytime you register a new version of a flow, Prefect API will automatically "archive" the old version in place of the newly registered flow. Archiving means that the old version's schedule is set to "Paused" and no new flow runs can be created.

```graphql
mutation {
  archive_flow(input: { flow_id: "your-flow-id-here" }) {
    id
  }
}
```

## Flow Settings <Badge text="GQL"/>

Running your flows with a Prefect backend has several insurance policies to ensure flows run healthily and robustly. Three such policies are:

- Flow and task run heartbeats
- [Lazarus](services.html#lazarus) resurrections
- and version locking

These safeguards can be toggled on a flow-by-flow basis using flow settings.

!!! warning Disabling safeguards
    Disabling these safeguards can alter fundamental assumptions about how flows run in Cloud. Be sure to read the docs and understand how each of these settings alters flow behavior in Cloud.


### Toggling Heartbeats

When running flows registered with a backend, Prefect Core sends heartbeats to the API every 30 seconds. These heartbeats are used to confirm the flow run and its task runs are healthy, and runs missing four heartbeats in a row will be marked as `Failed` by the [Zombie Killer](services.html#zombie-killer). For most users, this is a useful safeguard. In some cases, however, this is not useful to users. To prevent this, users may disable flow heartbeats, which will disable heartbeats and the Zombie Killer for runs of this flow. To do so, use the following GraphQL mutation:

```graphql
mutation {
  disable_flow_heartbeat(input: { flow_id: "your-flow-id-here" }) {
    success
  }
}
```

To reenable heartbeats for a flow, run the following GraphQL mutation:

```graphql
mutation {
  enable_flow_heartbeat(input: { flow_id: "your-flow-id-here" }) {
    success
  }
}
```

### Toggling Lazarus

The Lazarus process is responsible for rescheduling flow runs under the circumstances described [here](services.html#lazarus). If this is not desirable behavior for your flow, use the following GraphQL mutation to disable it:

```graphql
mutation {
  disable_flow_lazarus_process(input: { flow_id: "your-flow-id-here" }) {
    success
  }
}
```

To reenable Lazarus resurrections for a flow, run the following GraphQL mutation:

```graphql
mutation {
  enable_flow_lazarus_process(input: { flow_id: "your-flow-id-here" }) {
    success
  }
}
```

### Toggle Version Locking <Badge text="Cloud"/>

Prefect Cloud's _opt-in_ version locking mechanism enforces the assertion that your work runs once _and only once_. To enable version locking for a flow and its tasks, use the following GraphQL mutation:

```graphql
mutation {
  enable_flow_version_lock(input: { flow_id: "your-flow-id-here" }) {
    success
  }
}
```

To disable this functionality again, run the following GraphQL mutation:

```graphql
mutation {
  disable_flow_version_lock(input: { flow_id: "your-flow-id-here" }) {
    success
  }
}
```
