# PagerDuty + Prefect

## Integration Benefits

* ***Notify on-call responders based on Prefect automation rules.***
* ***Send event data from Prefect with links to the flow run and agents that triggered the event.***
* ***Create high and low urgency incidents based on the severity of the event from the Prefect event payload.***
* ***(Coming Soon...) Depending on your preference, either create multiple integrations in a PagerDuty Service for corresponding Prefect flows 
  and agents or reuse an integration key to create multiple actions that can be used by many automation rules in Prefect***

## How it Works

Prefect users can define automations for flow runs and agents and then be alerted in PagerDuty. Automations can be set up to notify about flow run state changes, SLAs on scheduled flow runs and the health of agents. With the 
PagerDuty + Prefect integration you can set up an action(s) for one or more PagerDuty integration keys and then assign those actions to the automations. If a Prefect automation is triggered, Prefect will send an alert to the users incident queue in PagerDuty
to be actioned as a typical PagerDuty alert. 

## Requirements

***The user can create or delete an action with the User level role***

## Support

If you need help with this integration, please contact ***help@prefect.io***. 

## Integration Walkthrough (Coming Soon...)

### In PagerDuty

**Integrating With a PagerDuty Service**
1. From the **Configuration** menu, select **Services**.
2. There are two ways to add an integration to a service:
   * **If you are adding your integration to an existing service**: Click the **name** of the service you want to add the integration to. Then, select the **Integrations** tab and click the **New Integration** button.
   * **If you are creating a new service for your integration**: Please read our documentation in section [Configuring Services and Integrations](https://support.pagerduty.com/docs/services-and-integrations#section-configuring-services-and-integrations) and follow the steps outlined in the [Create a New Service](https://support.pagerduty.com/docs/services-and-integrations#section-create-a-new-service) section, selecting ***PREFECT*** as the **Integration Type** in step 4. Continue with the In  ***PREFECT***  section (below) once you have finished these steps.
3. Enter an **Integration Name** in the format `monitoring-tool-service-name` (e.g.  ***PREFECT-FLOW-AUTOMATION-EXAMPLE***) and select  ***PREFECT***  from the Integration Type menu.
4. Click the **Add Integration** button to save your new integration. You will be redirected to Prefect to create an action.

### In ***PREFECT***

After creating a ***PREFECT*** integration in PagerDuty, you will be redirected to the PagerDuty integration page in Prefect. The integration keys with their corresponding PagerDuty Service names will be auto-populated
for you to save as action. You have the option to change the severity for each of these actions. These actions once saved can then be used by an automation. You also have the option to add additional rows so that you can 
pre-configure actions with different severity levels on the same integration key to be used by different automation rules. 

## How to Test the Action

1. In Prefect, navigate to Team > Automation Actions
2. Test the action from this screen with the debug icon

## How to Uninstall

1. In Prefect, navigate to Team > Automation Actions
2. Delete the action from this screen with the trash icon