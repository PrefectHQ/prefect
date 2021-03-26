
# Automations

Automations allow you to take action (such as cancelling a flow run or sending a notification to certain endpoints) when your flow or agent encounters a certain event.  

For example, you can send a Slack message to your team when a run from a production-critical flow has failed, along with the reason for the failure, so you can respond immediately. Or you can cancel a run that has been running (or scheduled) for more than an hour.  The Prefect backend API currently supports notification actions for Slack, Twilio, Pager Duty, and email.

You can set up and edit your Automations using the [API](/orchestration/concepts/api.html) or the Automations page in the UI.

## Events

Current events that you can monitor are:
- A flow run enters a given state; 
- Runs from multiple (or even all) flows enter a given state;
- A Flow run fails to start after being scheduled for a certain amount of time; 
- A Flow run fails to finish after running for a certain amount of time; 
- All agents with the same agent-config-id become unhealthy. 

## Actions

### Slack Action

To set up a Slack Action, you will need to create an incoming webhook for your slack channel.  [Slack's docs](https://api.slack.com/messaging/webhooks) talk you through how to create a Slack app and create an incoming webhook (and it's even easier than that sounds!)

Once you have an incoming webhook URL, you should store it as a secret in Team Settings and then select it when setting up the action. 

### Twilio Action

A Twilio Action needs a few more inputs: an Auth Token (which should be stored as a secret in the UI Team Settings), an Account SID, a Messaging Service SID and at least one phone number.

The phone number is the number that you want alerts to be sent to.

The Auth Token and Account SID are on your Twilio project dashboard.

The Messaging Service SID requires you to have a messaging service set up. These instructions are for the programmable SMS service.

1. Click on the "All Products and Services" option in the side-menu.

<div class="add-shadow">
  <img src="/orchestration/ui/twilio-sidenav.png">
</div>

<p>&nbsp;</p>

2. Select "Programmable SMS"
3. Select SMS
4. Click on the "Create New Messaging Service" icon

<div class="add-shadow">
  <img src="/orchestration/ui/twilio-new.png">
</div>

<p>&nbsp;</p>

5. Give your project a name and check the settings.
6. Click on 'Numbers' and add a number to your account. (This is not the number your messages will get sent to so you don't need to enter this in the Prefect Cloud Hooks form.)
7. Your Mesaging Service SID is the Service SID in the Settings page.

### Pager Duty Action

For a Pager Duty action, you'll need an API Token (which should be stored as a secret) and an Integration Key. You'll also need to select a Severity level from the dropdown menu.

The API Token comes from the API Access section of the Configuration menu of the Pager Duty dashboard.

<div class="add-shadow">
  <img src="/orchestration/ui/pager-duty-menu.png">
</div>

<p>&nbsp;</p>

To find your Integration Key, you also need the Configuration menu but choose Services. Select the service you want to add a Cloud Hook to and then click on the Integrations tab.

<div class="add-shadow">
  <img src="/orchestration/ui/pager-duty-integrations.png">
</div>

<p>&nbsp;</p>

In Integrations, select "New integration" and create a new integration using the API.

<div class="add-shadow">
  <img src="/orchestration/ui/pager-duty-new-integration.png">
</div>

<p>&nbsp;</p>

Your Integration Key will show in the integrations list.

<div class="add-shadow">
  <img src="/orchestration/ui/pager-duty-integration-key.png">
</div>

<p>&nbsp;</p>


<style>
.add-shadow  {
    width: 90%;
    max-height: auto;
    border-radius: 5px;
    vertical-align: bottom;
    z-index: -1;
    outline: 1;
    box-shadow: 0px 20px 15px #3D4849;
}
</style>
