---
description: An event is a notification of a change from a resource
tags:
    - resources
    - events
    - observability
---

# Events <span class="badge cloud"></span>

An event is a notification of a change. Together, events form a feed of activity recording what's happening across your stack. Events power several features in Prefect Cloud, including flow run logs, audit logs, and automations. Events can represent API calls, state transitions, or changes in your execution environment or infrastructure. Events enable observability into your data stack via the [event feed](/ui/events/), and the configuration of Prefect's reactivity via [automations](/ui/automations/).

![Prefect UI](../img/ui/event-feed.png)

## Event Specificiation

Events adhere to a structured [specification](https://app.prefect.cloud/api/docs#tag/Events).

![Prefect UI](../img/ui/event-spec.png)
  
| Name | Type | Required? | Description |
| ---- | ---- | --------- | ----------- |
| occurred |  String | yes | When the event happened |
| event |  String | yes | The name of the event that happened |
| resource|  Object | yes | The primary Resource this event concerns |
| related | Array | no | A list of additional Resources involved in this event |
| payload | Object | no | An open-ended set of data describing what happened |
| id | String | yes | The client-provided identifier of this event |
| follows | String | no | The ID of an event that is known to have occurred prior to this one. |


## Event Grammar

Generally, events have a consistent and informative grammar - an event describes a resource and an action that the resource took or that was taken on that resource. For example, events emitted by Prefect objects take the form of:


```
prefect.block.write-method.called
prefect-cloud.automation.action.executed
prefect-cloud.user.logged-in
```

## Event Sources

Events are automatically emitted by all Prefect objects, including flows, tasks, deployments, work queues, and logs. Prefect-emitted events will contain the `prefect` or `prefect-cloud` resource prefix. Events can also be sent to the Prefect [events API](https://app.prefect.cloud/api/docs#tag/Events) via authenticated http request.

The Prefect SDK provides a method that emits events, for use in arbitrary python code that may not be a task or 
flow. Running the following code will emit events to Prefect Cloud, which will validate and ingest the event data.


```python3
from prefect.events import emit_event

def some_function(name: str="kiki") -> None:
    print(f"hi {name}!")
    emit_event(event=f"{name}.sent.event!", resource=f"prefect.resource.id":"coder.{name}")
          
some_function()
```

Emitted events will appear in the [event feed](/ui/events/) where you can visualize activity in context and configure [automations](/ui/automations/) to react to the presence or absence of it in the future.


## Resources

Every event has a primary resource, which describes the object that emitted an event. Resources are used as quasi-stable identifiers for sources of events, and are constructed as dot-delimited strings, for example:

```
prefect-cloud.automation.5b9c5c3d-6ca0-48d0-8331-79f4b65385b3.action.0
acme.user.kiki.elt_script_1
prefect.flow-run.e3755d32-cec5-42ca-9bcd-af236e308ba6
```

Resources can optionally have additional arbitrary labels which can be used in event aggregation queries, such as:

```json
"resource": {
    "prefect.resource.id": "prefect-cloud.automation.5b9c5c3d-6ca0-48d0-8331-79f4b65385b3",
    "prefect-cloud.action.type": "call-webhook"
    }
```

Events can optionally contain related resources, used to associate the event with other resources, such as in the case that the primary resource acted on or with another resource:

```json
"resource": {
    "prefect.resource.id": "prefect-cloud.automation.5b9c5c3d-6ca0-48d0-8331-79f4b65385b3.action.0",
    "prefect-cloud.action.type": "call-webhook"
  },
"related": [
  {
      "prefect.resource.id": "prefect-cloud.automation.5b9c5c3d-6ca0-48d0-8331-79f4b65385b3",
      "prefect.resource.role": "automation",
      "prefect-cloud.name": "webhook_body_demo",
      "prefect-cloud.posture": "Reactive"
  }
]
```






