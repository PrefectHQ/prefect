---
description: Configure automations based on flow state from the Prefect UI and Prefect Cloud.
icon: material/cloud-outline
tags:
    - Orion
    - UI
    - states
    - flow runs
    - events
    - triggers
    - Prefect Cloud
---

# Automations <span class="badge cloud"></span>

Automations in Prefect Cloud allow for increased flexibility and control of your data stack by allowing you to configure [triggers](#triggers) and [actions](#actions). Using triggers and actions you can automatically kick off flow runs, pause deployments, or send custom notifications in response to real-time monitoring events.

The **Automations** page provides an overview of all configured automations for your workspace.

![Viewing automations for a workspace in Prefect Cloud.](/img/ui/automations.png)

Selecting the toggle next to an automation pauses execution of the automation. 

The button next to the toggle provides commands to copy the automation ID, edit the automation, or delete the automation.

On the **Automations** page, select the **+** icon to create a new automation. You'll be prompted to configure:

- A [trigger](#triggers) condition that causes the automation to execute.
- One or more [actions](#actions) carried out by the automation.
- [Details](#details) about the automation, such as a name and description.

## Triggers

Triggers specify the conditions under which your action should be performed. Triggers can be of several types, including triggers based on: 

- Flow run state change
- Work queue health

Importantly, triggers can be configured not only in reaction to events, but also proactively: to trigger in the absence of an event you expect to see.

![Configuring a trigger for an automation in Prefect Cloud.](/img/ui/automations-trigger.png)

For example, in the case of flow run state change triggers, you might expect production flows to finish in no longer than thirty minutes. But transient infrastructure or network issues could cause your flow to get “stuck” in a running state. A trigger could kick off an action if the flow stays in a running state for more than 30 minutes. This action could be on the flow itself, such as canceling or restarting it, or it could take the form of a notification so someone can take manual remediation steps.

!!! note "Work queue health"
    A work queue is "unhealthy" if it has not been polled in over 60 seconds and has one or more late runs.

## Actions

Actions specify what your automation does when its trigger criteria are met. Current action types include: 

- Cancel a flow run
- Pause or resume a deployment schedule
- Run a deployment
- Pause or resume a work queue
- Send a [notification](#automation-notifications)

![Configuring an action for an automation in Prefect Cloud.](/img/ui/automations-action.png)

### Selected and inferred action targets

Some actions require you to either select the target of the action, or specify that the target of the action should be inferred. 

Selected targets are simple, and useful for when you know exactly what object your action should act on &mdash; for example, the case of a cleanup flow you want to run or a specific notification you’d like to send.

Inferred targets are deduced from the trigger itself. 

For example, if a trigger fires on a flow run that is stuck in a running state, and the action is to cancel an inferred flow run, the flow run to cancel is inferred as the stuck run that caused the trigger to fire. 

Similarly, if a trigger fires on work queue health and the action is to pause an inferred work queue, the work queue to pause is inferred as the unhealthy work queue that caused the trigger to fire. 

Prefect tries to infer the relevant event whenever possible, but sometimes one does not exist.

## Details

Specify a name and, optionally, a description for the automation.

![Configuring details for an automation in Prefect Cloud.](/img/ui/automations-details.png)

## Automation notifications

Notifications enable you to set up automation actions that send a message. 

Automation notifications support sending notifications via any predefined block that is capable of and configured to send a message. That includes, for example:

- Slack message to a channel
- Microsoft Teams message to a channel
- Email to a configured email address

![Configuring notifications for an automation in Prefect Cloud.](/img/ui/automations-notifications.png)

!!! note "Notification blocks must be pre-configured"
    Notification blocks must be pre-configured prior to creating a notification action. Any existing blocks capable of sending messages will be shown in the block drop-down list.

    The **Add +** button cancels the current automation creation process and enables configuration a notification block.

## Templating notifications with Jinja

The notification body can include templated variables using [Jinja](https://palletsprojects.com/p/jinja/) syntax. Templated variable enable you to include details relevant to automation trigger, such as a flow or queue name. 

Jinja templated variable syntax wraps the variable name in double curly brackets, like `{{ variable }}`.

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

## Automations API 

The [automations API](https://app.prefect.cloud/api/docs#tag/Automations) enables further programatic customization of trigger and action policies based on arbitrary [events](https://app.prefect.cloud/api/docs#tag/Events).
