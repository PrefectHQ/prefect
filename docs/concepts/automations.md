---
description: Configure automations based on flow state from the Prefect UI and Prefect Cloud.
tags:
    - UI
    - states
    - flow runs
    - events
    - triggers
    - Prefect Cloud
    - automations
search:
  boost: 2
---

# Automations <span class="badge cloud"></span>

Automations in Prefect Cloud enable you to configure [actions](#actions) that Prefect executes automatically based on [trigger](#triggers) conditions related to your flows and work pools.

Using triggers and actions you can automatically kick off flow runs, pause deployments, or send custom notifications in response to real-time monitoring events.

!!! cloud-ad "Automations are only available in Prefect Cloud"
    [Notifications](/concepts/notifications/) in an open-source Prefect server provide a subset of the notification message-sending features available in Automations.

## Automations overview

The **Automations** page provides an overview of all configured automations for your workspace.

![Viewing automations for a workspace in Prefect Cloud.](/img/ui/automations.png)

Selecting the toggle next to an automation pauses execution of the automation.

The button next to the toggle provides commands to copy the automation ID, edit the automation, or delete the automation.

Select the name of an automation to view **Details** about it and relevant **Events**.

## Create an automation

On the **Automations** page, select the **+** icon to create a new automation. You'll be prompted to configure:

- A [trigger](#triggers) condition that causes the automation to execute.
- One or more [actions](#actions) carried out by the automation.
- [Details](#details) about the automation, such as a name and description.

### Triggers

Triggers specify the conditions under which your action should be performed. Triggers can be of several types, including triggers based on:

- Flow run state change
  - Note - Flow Run Tags currently are only evaluated with `OR` criteria
- Work pool status
- Deployment status
- Metric thresholds, such as average duration, lateness, or completion percentage
- Custom event triggers

!!! note "Automations API"
    The [automations API](https://app.prefect.cloud/api/docs#tag/Automations) enables further programmatic customization of trigger and action policies based on arbitrary [events](https://app.prefect.cloud/api/docs#tag/Events).

Importantly, triggers can be configured not only in reaction to events, but also proactively: to trigger in the absence of an event you expect to see.

![Configuring a trigger for an automation in Prefect Cloud.](/img/ui/automations-trigger.png)

For example, in the case of flow run state change triggers, you might expect production flows to finish in no longer than thirty minutes. But transient infrastructure or network issues could cause your flow to get “stuck” in a running state. A trigger could kick off an action if the flow stays in a running state for more than 30 minutes. This action could be on the flow itself, such as canceling or restarting it, or it could take the form of a notification so someone can take manual remediation steps.


### Actions

Actions specify what your automation does when its trigger criteria are met. Current action types include:

- Cancel a flow run
- Pause a flow run
- Run a deployment
- Pause or resume a deployment schedule
- Pause or resume a work queue
- Pause or resume an automation
- Send a [notification](#automation-notifications)
- Call a webhook
- Open an incident

![Configuring an action for an automation in Prefect Cloud.](/img/ui/automations-action.png)

### Selected and inferred action targets

Some actions require you to either select the target of the action, or specify that the target of the action should be inferred.

Selected targets are simple, and useful for when you know exactly what object your action should act on &mdash; for example, the case of a cleanup flow you want to run or a specific notification you’d like to send.

Inferred targets are deduced from the trigger itself.

For example, if a trigger fires on a flow run that is stuck in a running state, and the action is to cancel an inferred flow run, the flow run to cancel is inferred as the stuck run that caused the trigger to fire.

Similarly, if a trigger fires on a work queue event and the corresponding action is to pause an inferred work queue, the inferred work queue is the one that emitted the event.

Prefect tries to infer the relevant event whenever possible, but sometimes one does not exist.

Specify a name and, optionally, a description for the automation.

## Custom triggers

Custom triggers allow advanced configuration of the conditions on which an automation executes its actions. Several custom trigger fields accept values that end with trailing wildcards, like `"prefect.flow-run.*"`.

![Viewing a custom trigger for automations for a workspace in Prefect Cloud.](/img/ui/automations-custom.png)

The schema that defines a trigger is as follows:

| Name               | Type               | Supports trailing wildcards | Description |
| ------------------ | ------------------ | --------------------------- | ----------- |
| **match**          | object             | :material-check:            | Labels for resources which this Automation will match. |
| **match_related**  | object             | :material-check:            | Labels for related resources which this Automation will match. |
| **after**          | array of strings   | :material-check:            | Event(s), one of which must have first been seen to start this automation. |
| **expect**         | array of strings   | :material-check:            | The event(s) this automation is expecting to see. If empty, this automation will evaluate any matched event. |
| **for_each**       | array of strings   | :material-close:            | Evaluate the Automation separately for each distinct value of these labels on the resource. By default, labels refer to the primary resource of the triggering event. You may also refer to labels from related resources by specifying `related:<role>:<label>`. This will use the value of that label for the first related resource in that role. |
| **posture**        | string enum        | N/A                         | The posture of this Automation, either Reactive or Proactive. Reactive automations respond to the presence of the expected events, while Proactive automations respond to the absence of those expected events. |
| **threshold**      | integer            | N/A                         | The number of events required for this Automation to trigger (for Reactive automations), or the number of events expected (for Proactive automations) |
| **within**         | number             | N/A                         | The time period over which the events must occur. For Reactive triggers, this may be as low as 0 seconds, but must be at least 10 seconds for Proactive triggers |



### Resource matching

`match` and `match_related` control which events a trigger considers for evaluation by filtering on the contents of their `resource` and `related` fields, respectively. Each label added to a `match` filter is `AND`ed with the other labels, and can accept a single value or a list of multiple values that are `OR`ed together.

Consider the `resource` and `related` fields on the following `prefect.flow-run.Completed` event, truncated for the sake of example. Its primary resource is a flow run, and since that flow run was started via a deployment, it is related to both its flow and its deployment:

```json
"resource": {
  "prefect.resource.id": "prefect.flow-run.925eacce-7fe5-4753-8f02-77f1511543db",
  "prefect.resource.name": "cute-kittiwake"
}
"related": [
  {
    "prefect.resource.id": "prefect.flow.cb6126db-d528-402f-b439-96637187a8ca",
    "prefect.resource.role": "flow",
    "prefect.resource.name": "hello"
  },
  {
    "prefect.resource.id": "prefect.deployment.37ca4a08-e2d9-4628-a310-cc15a323378e",
    "prefect.resource.role": "deployment",
    "prefect.resource.name": "example"
  }
]
```

There are a number of valid ways to select the above event for evaluation, and the approach depends on the purpose of the automation.

The following configuration will filter for any events whose primary resource is a flow run, _and_ that flow run has a name starting with `cute-` or `radical-`.

```json
"match": {
  "prefect.resource.id": "prefect.flow-run.*",
  "prefect.resource.name": ["cute-*", "radical-*"]
},
"match_related": {},
...
```

This configuration, on the other hand, will filter for any events for which this specific deployment is a related resource.

```json
"match": {},
"match_related": {
  "prefect.resource.id": "prefect.deployment.37ca4a08-e2d9-4628-a310-cc15a323378e"
},
...
```

Both of the above approaches will select the example `prefect.flow-run.Completed` event, but will permit additional, possibly undesired events through the filter as well. `match` and `match_related` can be combined for more restrictive filtering:

```json
"match": {
  "prefect.resource.id": "prefect.flow-run.*",
  "prefect.resource.name": ["cute-*", "radical-*"]
},
"match_related": {
  "prefect.resource.id": "prefect.deployment.37ca4a08-e2d9-4628-a310-cc15a323378e"
},
...
```

Now this trigger will filter only for events whose primary resource is a flow run started by a specific deployment, _and_ that flow run has a name starting with `cute-` or `radical-`.

### Expected events

Once an event has passed through the `match` filters, it must be decided if this event should be counted toward the trigger's `threshold`. Whether that is the case is determined by the event names present in `expect`.

This configuration informs the trigger to evaluate _only_ `prefect.flow-run.Completed` events that have passed the `match` filters.

```json
"expect": [
  "prefect.flow-run.Completed"
],
...
```

`threshold` decides the quantity of `expect`ed events needed to satisfy the trigger. Increasing the `threshold` above 1 will also require use of `within` to define a range of time in which multiple events are seen. The following configuration will expect two occurrences of `prefect.flow-run.Completed` within 60 seconds.

```json
"expect": [
  "prefect.flow-run.Completed"
],
"threshold": 2,
"within": 60,
...
```

`after` can be used to handle scenarios that require more complex event reactivity.

Take, for example, this flow which emits an event indicating the table it operates on is missing or empty:

```python
from prefect import flow
from prefect.events import emit_event
from db import Table


@flow
def transform(table_name: str):
  table = Table(table_name)

  if not table.exists():
    emit_event(
        event="table-missing",
        resource={"prefect.resource.id": "etl-events.transform"}
    )
  elif table.is_empty():
    emit_event(
        event="table-empty",
        resource={"prefect.resource.id": "etl-events.transform"}
    )
  else:
    # transform data
```

The following configuration uses `after` to prevent this automation from firing unless either a `table-missing` or a `table-empty` event has occurred before a flow run of this deployment completes.

!!! tip
    Note how `match` and `match_related` are used to ensure the trigger only evaluates events that are relevant to its purpose.

```json
"match": {
  "prefect.resource.id": [
    "prefect.flow-run.*",
    "etl-events.transform"
  ]
},
"match_related": {
  "prefect.resource.id": "prefect.deployment.37ca4a08-e2d9-4628-a310-cc15a323378e"
}
"after": [
  "table-missing",
  "table-empty"
]
"expect": [
  "prefect.flow-run.Completed"
],
...
```

### Evaluation strategy

All of the previous examples were designed around a reactive `posture` - that is, count up events toward the `threshold` until it is met, then execute actions. To respond to the absence of events, use a proactive `posture`. A proactive trigger will fire when its `threshold` has _not_ been met by the end of the window of time defined by `within`. Proactive triggers must have a `within` of at least 10 seconds. 

The following trigger will fire if a `prefect.flow-run.Completed` event is not seen within 60 seconds after a `prefect.flow-run.Running` event is seen.

```json
{
  "match": {
    "prefect.resource.id": "prefect.flow-run.*"
  },
  "match_related": {},
  "after": [
    "prefect.flow-run.Running"
  ],
  "expect": [
    "prefect.flow-run.Completed"
  ],
  "for_each": [],
  "posture": "Proactive",
  "threshold": 1,
  "within": 60
}
```
However, without `for_each`, a `prefect.flow-run.Completed` event from a _different_ flow run than the one that started this trigger with its `prefect.flow-run.Running` event could satisfy the condition. Adding a `for_each` of `prefect.resource.id` will cause this trigger to be evaluated separately for each flow run id associated with these events.

```json
{
  "match": {
    "prefect.resource.id": "prefect.flow-run.*"
  },
  "match_related": {},
  "after": [
    "prefect.flow-run.Running"
  ],
  "expect": [
    "prefect.flow-run.Completed"
  ],
  "for_each": [
    "prefect.resource.id"
  ],
  "posture": "Proactive",
  "threshold": 1,
  "within": 60
}
```

## Create an automation via deployment triggers

To enable the simple configuration of event-driven deployments, Prefect provides deployment triggers - a shorthand for creating automations that are linked to specific deployments to run them based on the presence or absence of events.

```yaml
# prefect.yaml
deployments:
  - name: my-deployment
    entrypoint: path/to/flow.py:decorated_fn
    work_pool:
      name: my-process-pool
    triggers:
      - enabled: true
        match:
          prefect.resource.id: my.external.resource
        expect:
          - external.resource.pinged
        parameters:
          param_1: "{{ event }}"
```

At deployment time, this will create a linked automation that is triggered by events matching your chosen [grammar](/concepts/events/#event-grammar), which will pass the templatable `event` as a parameter to the deployment's flow run.

### Pass triggers to `prefect deploy`
You can pass one or more `--trigger` arguments to `prefect deploy`, which can be either a JSON string or a path to a `.yaml` or `.json` file.

```bash
# Pass a trigger as a JSON string
prefect deploy -n test-deployment \
  --trigger '{
    "enabled": true, 
    "match": {
      "prefect.resource.id": "prefect.flow-run.*"
    }, 
    "expect": ["prefect.flow-run.Completed"]
  }'

# Pass a trigger using a JSON/YAML file
prefect deploy -n test-deployment --trigger triggers.yaml
prefect deploy -n test-deployment --trigger my_stuff/triggers.json
```

For example, a `triggers.yaml` file could have many triggers defined:

```yaml
triggers:
  - enabled: true
    match:
      prefect.resource.id: my.external.resource
    expect:
      - external.resource.pinged
    parameters:
      param_1: "{{ event }}"
  - enabled: true
    match:
      prefect.resource.id: my.other.external.resource
    expect:
      - some.other.event
    parameters:
      param_1: "{{ event }}"
```
Both of the above triggers would be attached to `test-deployment` after running `prefect deploy`.


!!! warning "Triggers passed to `prefect deploy` will override any triggers defined in `prefect.yaml`"
    While you can define triggers in `prefect.yaml` for a given deployment, triggers passed to `prefect deploy` will
    take precedence over those defined in `prefect.yaml`.

Note that deployment triggers contribute to the total number of automations in your workspace.

## Automation notifications

Notifications enable you to set up automation actions that send a message.

Automation notifications support sending notifications via any predefined block that is capable of and configured to send a message. That includes, for example:

- Slack message to a channel
- Microsoft Teams message to a channel
- Email to a configured email address

![Configuring notifications for an automation in Prefect Cloud.](/img/ui/automations-notifications.png)

## Templating with Jinja

Automation actions can access templated variables through [Jinja](https://palletsprojects.com/p/jinja/) syntax. Templated variables enable you to dynamically include details from an automation trigger, such as a flow or pool name.

Jinja templated variable syntax wraps the variable name in double curly brackets, like this: `{{ variable }}`.

You can access properties of the underlying flow run objects including:

- [flow_run](/api-ref/server/schemas/core/#prefect.server.schemas.core.FlowRun)
- [flow](/api-ref/server/schemas/core/#prefect.server.schemas.core.Flow)
- [deployment](/api-ref/server/schemas/core/#prefect.server.schemas.core.Deployment)
- [work_queue](/api-ref/server/schemas/core/#prefect.server.schemas.core.WorkQueue)
- [work_pool](/api-ref/server/schemas/core/#prefect.server.schemas.core.WorkPool)

In addition to its native properties, each object includes an `id` along with `created` and `updated` timestamps.

The `flow_run|ui_url` token returns the URL for viewing the flow run in Prefect Cloud.

Here’s an example for something that would be relevant to a flow run state-based notification:

```
Flow run {{ flow_run.name }} entered state {{ flow_run.state.name }}. 

    Timestamp: {{ flow_run.state.timestamp }}
    Flow ID: {{ flow_run.flow_id }}
    Flow Run ID: {{ flow_run.id }}
    State message: {{ flow_run.state.message }}
```

The resulting Slack webhook notification would look something like this:

![Configuring notifications for an automation in Prefect Cloud.](/img/ui/templated-notification.png)

You could include `flow` and `deployment` properties.

```
Flow run {{ flow_run.name }} for flow {{ flow.name }}
entered state {{ flow_run.state.name }}
with message {{ flow_run.state.message }}

Flow tags: {{ flow_run.tags }}
Deployment name: {{ deployment.name }}
Deployment version: {{ deployment.version }}
Deployment parameters: {{ deployment.parameters }}
```

An automation that reports on work pool status might include notifications using `work_pool` properties.

```
Work pool status alert!

Name: {{ work_pool.name }}
Last polled: {{ work_pool.last_polled }}
```

In addition to those shortcuts for flows, deployments, and work pools, you have access to the automation and the event that triggered the automation. See the [Automations API](https://app.prefect.cloud/api/docs#tag/Automations) for additional details.

```
Automation: {{ automation.name }}
Description: {{ automation.description }}

Event: {{ event.id }}
Resource:
{% for label, value in event.resource %}
{{ label }}: {{ value }}
{% endfor %}
Related Resources:
{% for related in event.related %}
    Role: {{ related.role }}
    {% for label, value in event.resource %}
    {{ label }}: {{ value }}
    {% endfor %}
{% endfor %}
```

Note that this example also illustrates the ability to use Jinja features such as iterator and for loop [control structures](https://jinja.palletsprojects.com/en/3.1.x/templates/#list-of-control-structures) when templating notifications.
