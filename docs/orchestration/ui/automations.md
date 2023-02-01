# Automations <Badge text="Cloud"/>

<div style="border: 2px solid #27b1ff; border-radius: 10px; padding: 1em;">
Looking for the latest <a href="https://docs.prefect.io/">Prefect 2</a> release? Prefect 2 and <a href="https://app.prefect.cloud">Prefect Cloud 2</a> have been released for General Availability. See <a href="https://docs.prefect.io/">https://docs.prefect.io/</a> for details.
</div>

Automations allow you to configure actions when an event occurs in the Prefect ecosystem.

## Overview

The UI's Automation page provides the ability to create new automations &mdash;  actions such as cancelling a flow run or sending a notification when an event occurs in the Prefect ecosystem &mdash; and editable summaries of all automations created in your Prefect Cloud account.

Automations are only available in Prefect Cloud, and some automation features are limited to Prefect Cloud Standard plan and above.

See the [Automations](/orchestration/concepts/automations) documentation for details on automation features and configuration.

To create, edit, or review available automations, click **Automations** in the Prefect Cloud dashboard.

![Screenshot showing the automations page of Prefect Cloud](/orchestration/ui/automations_ui.png)

The **New Automation** area provides a mechanism for defining new automations.

The **Automations** area provides a listing of previously created automations.

## New Automations

The **New Automation** tool lets you define an automation using common "if...then" logic. Simply choose options to specify the event source, event type, and action. If an option is grayed out and shows a cloud tag, it requires upgrading your Prefect Cloud plan to the Standard plan or higher.

![Screenshot showing the initial automation event options](/orchestration/ui/automations_plan.png)

As you build the automation definition, the elements display as a description of the automation.

![Screenshot showing the automation state trigger options](/orchestration/ui/automations_new.png)

At the **Choose an action** step you can: 

- Select a built-in Prefect messaging action by clicking the **+ New** button.
- Select a system action such as pausing the schedule (**Standard plan and above**).
- Select a previously defined action such as the [PagerDuty integration](/orchestration/integrations/pagerduty.html).

Click **Save** to save your automation.

![Screenshot showing the automation actions options](/orchestration/ui/automations_actions.png)

If you click the **+ New** button to select a messaging action, you can select from the available built-in messaging triggers.

![Screenshot showing the automation messaging action options](/orchestration/ui/automations_msg.png)

## Automations

The **Automations** area provides a listing of previously defined automations. 

![Screenshot showing the listing of defined automations](/orchestration/ui/automations_list.png)

To delete an automation, click the **...** icon next to an automation, then click **Delete**.

To edit an automation, click anywhere on the automation tile and you'll enable a definition wizard similar to creating a new automation.

![Screenshot showing an automation selected for editing](/orchestration/ui/automations_edit.png)

## Automation Actions

An action is a response to an event. For each automation you can configure an [automation action](/orchestration/concepts/automations.html#actions) to happen when certain event conditions are met.

Create an action through the **Choose an action** step of creating [new automations](#new-automations) as described above.

To see details of actions configured for your team, click **Team > Automation Actions** or go directly to the [Automation Actions](https://cloud.prefect.io/team/actions) page in Prefect Cloud. There you can see a list of configured actions, test actions, and delete actions.

![Screenshot of team Automation Actions page in Prefect Cloud](/orchestration/ui/automation_actions.png)