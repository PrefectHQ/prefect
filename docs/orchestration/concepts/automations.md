# Automations 

Automations allow you to configure actions (such as cancelling a flow run or sending a notification to certain endpoints) when your flows or agents encounter certain events.

For example, you can send a Slack message to your team when a run from a production critical flow has failed, along with the reason for the failure so that you can respond immediately. Or you can cancel a run that has been running (or scheduled) for more than an hour to enforce SLAs.  

You can set up and edit your Automations using the [API](/orchestration/concepts/api.html) or the Automations page in the UI.

## Events

An _event_ is a configurable condition that, when met, will cause an automation to run. Currently you can configure automations for the following events:
- A flow run enters a given state or states
- Runs from multiple (or all!) flows enter a given state or states

Additionally, if you are a Standard Tier user in Prefect Cloud, you can also configure automations for the following scenarios:
- A flow run fails to start after being scheduled for a certain amount of time
- A flow run fails to finish after running for a certain amount of time
- Some number of agents with the same [`agent_config_id`](orchestration/agents/overview.html#health-checks) become unhealthy

## Actions

An _action_ is a response on the event. Within your automation you can configure an action to happen when certain event conditions are met. For example, if your flow run fails (the event) you can cancel the run (the action).  

You can configure actions which send notifications using the following services:

- Slack
- Twilio
- PagerDuty
- MS Teams
- Email

Moreover, if you are on a Standard or Enterprise plan you can also configure an action to cancel a flow run. 

### Action Messages

Notification actions have a default message which varies depending on what type of action you attach the config to. You can also configure your action to include a custom message. 

### Custom Messages

You can use the following attributes to send a custom message:

For automations connected to a flow run state change:
- flow_run_name
- flow_name
- state
- state_message
- flow_run_link

For automations connected to a flow SLA event:
- flow_run_name
- flow_name
- flow_run_id
- kind
- flow_sla_config_id
- duration_seconds
- flow_run_link

For automations connected to a agent SLA event:
- agent_config_id
- sla_min_healthy
- agent_ids


#### Default Messages

For a state change event the message would be: "Run {flow_run_name} of flow {flow_name} entered state {state} with message {state_message}. See {flow_run_link} for more details."
For a flow SLA event the default message would be: "Run {flow_run_name} ({flow_run_id}) of flow {flow_name} failed {kind} SLA ({flow_sla_config_id}) after {duration_seconds} seconds. See {flow_run_link} for more details."
For an agent SLA event, the default message would be: "Agents sharing the config {agent_config_id} have failed the minimum healthy count of {sla_min_healthy}. The following agents are unhealthy: {agent_ids}"


