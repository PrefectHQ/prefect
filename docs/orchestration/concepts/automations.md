# Automations 

Automations allow you to configure actions (such as cancelling a flow run or sending a notification to certain endpoints) when your flows or agents encounter certain events.

For example, you can send a Slack message to your team when a run from a production critical flow has failed, along with the reason for the failure so that you can respond immediately. Or you can cancel a run that has been running (or scheduled) for more than an hour to enforce SLAs.  The Prefect Cloud API currently supports notification actions for Slack, Twilio, Pager Duty, email and arbitrary webhooks.

You can set up and edit your Automations using the [API](/orchestration/concepts/api.html) or the Automations page in the UI.

## Events

An _event_ is a configurable condition that, when met, will cause an automation to run. Currently you can configure automations for the following events:
- A flow run enters a given state or states
- Runs from multiple (or all!) flows enter a given state or states

Additionally, if you are a Standard Tier user in Prefect Cloud, you can also configure automations for the following scenarios:
- A flow run fails to start after being scheduled for a certain amount of time
- A flow run fails to finish after running for a certain amount of time
- Some number of agents with the same `agent_config_id` become unhealthy

## Actions

An action is a response on the event. Within your automation you can configure an action to happen when certain event conditions are met. For example, if your flow run fails (the event) you can cancel the run (the action).  

You can configure actions which send notifications using the following services:

Slack
Twilio
PagerDuty
MS Teams
Email

Moreover, if you are on a Standard or Enterprise plan you can also configure an action to cancel a flow run. 




