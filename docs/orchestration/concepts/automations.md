# Automations 

Automations allow you to configure actions (such as cancelling a flow run or sending a notification to certain endpoints) when an event occurs in the Prefect ecosystem.

For example, you can send a Slack message to your team when a run from a production critical flow has failed, along with the reason for the failure so that you can respond immediately. Or you can cancel a run that has been running (or scheduled) for more than an hour to enforce SLAs.  

The automations system is composed of events and actions. When an _event_ is paired with an _action_, we call it an _automation_. 

When creating an automation, you:
- Choose an event type
- Place filters or conditions on the event data
- Select an action to fire when the event occurs and the conditions are met

The following documentation will cover the various types of events and actions you can configure.

We recommend creating and managing your automations in the [UI Automations page](https://cloud.prefect.io/?automations). You can also manage automations via the GraphQL API, but it requires a deeper understanding of the system then this document will cover.

## Events

An event is something that occurs in the Prefect backend. 

Currently you can configure automations for the following events:
- Flow runs from a single, multiple, or all flows enter a given state or states
- A flow run fails to start after being scheduled for a certain amount of time (**Standard plan and above**)
- A flow run fails to finish after running for a certain amount of time  (**Standard plan and above**)
- Some number of agents with the same [`agent_config_id`](orchestration/agents/overview.html#health-checks) become unhealthy  (**Standard plan and above**)

::: tip Hooks
When you create an automation in the UI, you are actually creating a `Hook` between an `Event` type and an `Action` instance. This name difference will be apparent if you are attempting to work with automations by calling the GraphQL API directly
:::

## Actions

An _action_ is a response to the event. For each automation you can configure an action to happen when certain event conditions are met. For example, if your flow run fails (the event) you can cancel the run (the action).  

You can configure actions which send notifications using the following services:

- Slack
- Twilio
- PagerDuty
- Microsoft Teams
- Email


If you are on a Standard or Enterprise plan you can also configure Prefect API actions. These allow you to do the following:

- Cancel a flow run
- Pause a flow's schedule


## Messages

All events have a message associated with them. These events are templated when the event is created. For example, the flow run state change event has the message template:

`Run {flow_run_name} of flow {flow_name} entered state {state} with message {state_message}. See {flow_run_link} for more details.`


Actions with a message will generally default to using the event's message but allow you to override the message with a templatable string. For example, you may want to modify the above message to be more specific to your use-case:

`Run for client {flow_run_name} failed: {state_message}. Please investigate at {flow_run_link}.`

See [the reference](#events-reference) for more details on the attributes you can use to template messages.

## Reference

### Events reference

#### Base event

All event types provide the following attributes:
- `event_name`: The readable name of the event type
- `message`: A message specific to the event type
- `tenant_id`: The tenant id the event was created in
- `tenant_slug`: The slug of the tenant the event was created in
- `timestamp`: A timestamp indicating when the event occurred
- `id`: A unique id identifying this event

#### Flow run state change

**Attributes**

- `flow_id`
- `flow_name`
- `flow_group_id`
- `flow_link`
- `flow_run_id`
- `flow_run_name`
- `state`
- `state_message`
- `flow_run_link`

**Default message**

`Run {flow_run_name} of flow {flow_name} entered state {state} with message {state_message}. See {flow_run_link} for more details.`

#### Flow SLA failure

This event fires if a flow is late to start or late to finish. Specifically, you can configure an SLA one of the following:

- The flow has not entered a running state some time after the scheduled start time
- The flow has not entered a finished state some time after entering a running state 

**Attributes**

- `flow_id`
- `flow_name`
- `flow_group_id`
- `flow_link`
- `flow_run_id`
- `flow_run_name`
- `state`
- `state_message`
- `flow_run_link`
- `flow_sla_config_id`
- `kind`
- `duration_seconds`

**Default message**

`Run {flow_run_name} ({flow_run_id}) of flow {flow_name} failed {kind} SLA ({flow_sla_config_id}) after {duration_seconds} seconds. See {flow_run_link} for more details.`

#### Agent SLA failure

This event fires if a group of agents have not queried the backend after an amount of time. The "agent config" abstraction allows us to link multiple agents to a single key. The UI will create an agent config for you when you create an agent SLA automation.

If _no_ agents linked to the config are querying the API for flow runs, the SLA failure event will fire. If _any_ of the agents are healthy, the SLA will pass.

**Attributes**

- `healthy_agent_ids`
- `unhealthy_agent_ids`
- `sla_min_healthy`
- `agent_config_id`

**Default message**

`Agents sharing the config {agent_config_id} have failed the minimum healthy count of {sla_min_healthy}. The following agents are unhealthy: {agent_ids}`

### Actions reference

#### WebhookAction

Sends a payload to the given url when an event fires. 

Expects a 200 OK response or the action will be marked as failed.

**Configuration**

- `url`: The URL to send the payload to
- `payload`: Optional, a JSON payload to send to the URL. If not specified, all event data is dumped. Templatable.
- `headers`: Optional, JSON headers to include in the request. If not specified, defaults to include the event id: `{"X-PREFECT-EVENT-ID": "{id}"}`.  Templatable.

**Templating**

Both the payload and the header JSON can be templated using event attributes. For example, we can include our tenant id in the headers instead of the event id.

```json
headers = {"X-PREFECT-TENANT-ID": "{tenant_id}"}
```

Event data can be templated into both keys and values.

#### SlackNotificationAction

Send a notification using a Slack webhook.

**Configuration**

- `webhook_url_secret`: The name of the Prefect Secret with the Slack webhook URL
- `message`: Optional, a custom message to send

#### TeamsWebhookNotificationAction

Send a notification using a Microsoft Teams webhook.

**Configuration**

- `webhook_url_secret`: The name of the Prefect Secret with the Teans webhook URL
- `message`: Optional, a custom message to send. Templatable.
- `title`: Optional, a custom title to use for the message. Templatable.

#### EmailNotificationAction

Send an email notification.

**Configuration**

- `to_emails`: A list of email addresses to send an email to
- `subject`: Optional, a custom email subject. Templatable.
- `body`: Optional, a custom email body. Templatable.

#### TwilioNotificationAction

Send a text message notification with Twilio.

**Configuration**

- `account_sid`: The Twilio account SID
- `auth_token_secret` The name of the Prefect Secret with the Twilio auth token
- `messaging_service_sid`: The Twilio messaging service SID
- `phone_numbers`: A list of phone numbers to message
- `message`: Optional, a custom text message. Templatable.

#### PagerDutyNotificationAction

Send a notification using PagerDuty.

**Configuration**

- `api_token_secret`: The name of the Prefect Secret with the PagerDuty API token
- `routing_key`: The PagerDuty routing key
- `severity`: The PagerDuty severity to send a message on. One of: info, warning, error, critical
- `message`: Optional, a custom message. Templatable.

#### CancelFlowRunAction

Cancel a flow run. This action _must_ be hooked to an event that provides a `flow_run_id` to cancel.

**Configuration**

- `message`: Optional, a custom text message. Templatable.

#### PauseScheduleAction

Pause scheduling additional flow runs for a flow group.

**Configuration**

- `flow_group_id`: Optional, the UUID of a flow group to pause the schedule of. If not provided, this action _must_ be hooked to an event that provides it.
