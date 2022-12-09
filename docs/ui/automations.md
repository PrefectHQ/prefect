---
description: Configure notifications based on flow state from the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - states
    - flow runs
    - events
    - triggers
    - Prefect Cloud
---

# Automations <span class="badge cloud"></span> <span class="badge beta"></span>

Automations are currently in beta and under active development, with new features being added weekly. Reach out to [support@prefect.io](mailto:support@prefect.io) if you’re interested in getting early access.

Automations in Prefect Cloud allow for increased flexibility and control of your data stack by allowing you to configure [triggers](#triggers) and [actions](#actions). Using triggers and actions you can automatically kick off flow runs, pause deployments, or send custom notifications (coming soon!) in response to real-time monitoring events.

## Triggers

Triggers specify the conditions under which your action should be performed. Triggers can be of several types, including triggers based on: 

- Flow run state change
- Work queue health (coming soon!)

Importantly, triggers can be configured not only in reaction to events, but also proactively: to trigger in the absence of an event you expect to see.

For example, in the case of flow run state change triggers, you might expect production flows to finish in no longer than thirty minutes. But transient infrastructure or network issues could cause your flow to get “stuck” in a running state. A trigger could kick off an action if the flow stays in a running state for more than 30 minutes. This action could be on the flow itself, such as canceling or restarting it, or it could take the form of a notification so someone can take manual remediation steps.


## Actions

Actions specify what your automation does when its trigger criteria are met. Current action types include: 

- Starting a flow run
- Pausing/resuming a deployment schedule

### Selected and inferred action targets

Some actions require you to either select the target of the action, or specify that the target of the action should be inferred. 

Selected targets are simple, and useful for when you know exactly what object your action should act on &mdash; for example, the case of a cleanup flow you want to run or a specific notification you’d like to send.

Inferred targets are deduced from the trigger itself. 

For example, if a trigger fires on a flow run that is stuck in a running state, and the action is to cancel an inferred flow run, the flow run to cancel is inferred as the stuck run that caused the trigger to fire. 

Similarly, if a trigger fires on work queue health and the action is to pause an inferred work queue, the work queue to pause is inferred as the unhealthy work queue that caused the trigger to fire. 

Prefect tries to infer the relevant event whenever possible, but sometimes one does not exist.

## Coming soon

Automations will be the foundation of several new solutions in Prefect. In addition to triggers based on work queue health and flow run state changes, we’ll soon expand the types of conditions for triggers, including triggers based on infrastructure or block method events.  

We’ll also continue to expand the [automations API](https://app.prefect.cloud/api/docs#tag/Automations), which allows for further customization of trigger and action policies based on arbitrary [events](https://app.prefect.cloud/api/docs#tag/Events).
