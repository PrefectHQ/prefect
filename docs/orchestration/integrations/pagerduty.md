# PagerDuty + Prefect

Using the PagerDuty integration with Prefect, you can receive PagerDuty alerts based on events raised by your flow runs and agents.

## Integration benefits

* Notify on-call responders based on Prefect automation rules.
* Send event data from Prefect with links to the flow run and Agent that triggered the event.
* Create high- and low-urgency incidents based on the severity of the event from the Prefect event payload.
* Create multiple integrations in a PagerDuty service for corresponding Prefect flows and agents. 
* Use a single integration key to create multiple actions that can be used by many automation rules in Prefect.

## How it works

You can define [automations](/orchestration/concepts/automations.html) for flow runs and agents, then be alerted in PagerDuty. Automations can be set up to notify about flow run state changes, SLAs on scheduled flow runs, and the health of agents. 

With the PagerDuty + Prefect integration you can set up actions for one or more PagerDuty integration keys, then assign those actions to the automations. If a Prefect automation is triggered, Prefect sends an alert to the incident queue in PagerDuty. 

## Requirements

The PagerDuty integration requires Prefect automations, which are supported in [Prefect Cloud plans](https://www.prefect.io/pricing/).

Teams using [Role Based Access Controls (RBAC)](/orchestration/rbac/overview.html) need to set appropriate User level permissions to create, update, and delete automations.

## Support

If you need help with this integration, we have a public [Slack](https://prefect.io/slack) for chatting about Prefect, asking questions, and sharing tips, or contact us directly at _help@prefect.io_. 

## Setup and configuration

Follow these steps to set up the PagerDuty + Prefect integration.

Note that you should have PagerDuty and Prefect Cloud accounts created before starting the integration.

### In PagerDuty

First, make sure you have a configured PagerDuty service to connect with Prefect. From the **Configuration** menu in PagerDuty, select **Services**.

There are two ways to add an integration to a PagerDuty service:

* **If you are adding your integration to an existing service**: Click the **name** of the service you want to add the integration to. Then, select the **Integrations** tab and click the **New Integration** button.
* **If you are creating a new service for your integration**: Please read the PagerDuty documentation [Configuring Services and Integrations](https://support.pagerduty.com/docs/services-and-integrations#section-configuring-services-and-integrations) and follow the steps outlined in the [Create a New Service](https://support.pagerduty.com/docs/services-and-integrations#section-create-a-new-service) section, selecting **Prefect Cloud** as the **Integration Type** in step 4. Continue with the [In Prefect](#in-prefect) section below once you have finished these steps.

Enter an **Integration Name** in the format `monitoring-tool-service-name` (for example, "PREFECT-FLOW-AUTOMATION-EXAMPLE") and select **Prefect Cloud** from the **Integration Type** menu.

Click the **Add Integration** button to save your new integration. You will be redirected to Prefect to create an action.

### In Prefect

Once you have set up the PagerDuty service, click the following button or [use this link](https://app.pagerduty.com/install/integration?app_id=PC2USS4&redirect_url=https://cloud.prefect.io/pagerduty&version=2) to configure the integration: 

[<img src="/logos/pagerduty_green.png" height=62 width=300 style="max-height: 80px; max-width: 400px;">](https://app.pagerduty.com/install/integration?app_id=PC2USS4&redirect_url=https://cloud.prefect.io/pagerduty&version=2)

Log into your PagerDuty account and follow the PagerDuty steps, which include selecting the PagerDuty service. 

You will be redirected to Prefect Cloud. The PagerDuty integration keys, with their corresponding PagerDuty service names, will be auto-populated for you in Prefect Cloud to save as an action. You can change the severity for each of these actions. 

![](/orchestration/integrations/pagerduty_action.png)

Once saved, the actions can then be used by an [automation](/orchestration/concepts/automations.html). You also have the option to add additional rows so that you can pre-configure actions with different severity levels on the same integration key to be used by different automation rules.

## Test PagerDuty actions

Follow these steps to test a PagerDuty integration action:

1. In Prefect Cloud, navigate to **Team > Automation Actions**.
2. Test the action from this screen by clicking the **Test Action** (debug) button.

## Uninstall the PagerDuty integration

Follow these steps to remove the PagerDuty integration:

1. In Prefect Cloud, navigate to **Team > Automation Actions**.
2. Delete the action by clicking the **Delete Action** (trash icon) button.
