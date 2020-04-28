
# Cloud Hooks <Badge text="Cloud"/>

Cloud Hooks allow you to send notifications to certain endpoints, such as Slack, Twilio, Pager Duty and email, when your flow enters a given state. For example, you can send a Slack message to your team when a production-critical flow has failed, along with the reason for the failure, so you can respond immediately.

You can set up and edit your Cloud Hooks using the [API](/orchestration/concepts/api.html) or the Flow Settings page in the UI. 

<div class="add-shadow">
  <img src="/orchestration/ui/cloud-hook-email.png">
</div>

## Set Up
For all Cloud Hooks, you can choose a name for the hook (the default is 'Custom') and decide which states you want to be alerted about. However, different types of hook, need different inputs to set up.

### Email Cloud Hook

To set up an email Cloud Hook, decide which email you want your alerts to go to and enter it into the "To" section. 

### Web Cloud Hook

To set up a web Cloud Hook, enter the URL endpoint that you want Prefect to send a JSON payload to when your flow enters whatever states you want alerted about. 

### Slack Cloud Hook

To set up a Slack Cloud Hook, you will need to create an incoming webhook for your slack channel.  [Slack's docs](https://api.slack.com/messaging/webhooks) talk you through how to create a Slack app and create an incoming webhook (and it's even easier than that sounds!) 

Once you have an incoming webhook URL, you can copy it into the 'Slack URL' section of the Slack Cloud Hook form. 

### Twilio Cloud Hook

A Twilio Cloud Hook needs a few more inputs:  an Auth Token, an Account SID, a Messaging Service SID and at least one phone number. 





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




