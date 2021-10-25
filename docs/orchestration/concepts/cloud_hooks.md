
# Cloud Hooks

*Psst! We have recently added [Automations](/orchestration/concepts/automations.html) which offer more functionality than Cloud Hooks and will eventually replace them.*

Cloud Hooks allow you to send notifications to certain endpoints when your flow enters a given state. For example, you can send a Slack message to your team when a production-critical flow has failed, along with the reason for the failure, so you can respond immediately. The Prefect backend API currently supports hooks for Slack, Twilio, Pager Duty, email, and a more general Webhook.

You can set up and edit your Cloud Hooks using the [API](/orchestration/concepts/api.html) or the Flow Settings page in the UI.

## UI

For all Cloud Hooks, you can choose a name for the hook (the default is 'Custom') and decide which states you want to be alerted about. Different inputs are required depending on the type of Cloud Hook.

<div class="add-shadow">
  <img src="/orchestration/ui/cloud-hook-email.png">
</div>

<p>&nbsp;</p>

### Email Cloud Hook

To set up an Email Cloud Hook, enter an email in the "To" section. The email you enter will receive formatted emails that contain state updates and a link to the flow for which this Cloud Hook is configured.

### Web Cloud Hook

The Web Cloud Hook operates as an all-purpose webhook and can hit any endpoint.

To set up a Web Cloud Hook, enter the URL that you want Prefect to POST a JSON payload to when your flow enters your configured states.

### Slack Cloud Hook

To set up a Slack Cloud Hook, you will need to create an incoming webhook for your slack channel.  [Slack's docs](https://api.slack.com/messaging/webhooks) talk you through how to create a Slack app and create an incoming webhook (and it's even easier than that sounds!)

Once you have an incoming webhook URL, you can copy it into the 'Slack URL' section of the Slack Cloud Hook form.

### Twilio Cloud Hook

A Twilio Cloud Hook needs a few more inputs: an Auth Token, an Account SID, a Messaging Service SID and at least one phone number.

The phone number is the number that you want alerts to be sent to.

The Auth Token and Account SID are on your Twilio project dashboard.

<div class="add-shadow">
  <img src="/orchestration/ui/twilio-dashboard.png">
</div>

<p>&nbsp;</p>

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

### Pager Duty Cloud Hook

For a Pager Duty token, you'll need an API Token and an Integration Key. You'll also need to select a Severity level from the dropdown menu.

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

## API
To create a Cloud Hook using the [API](/orchestration/concepts/api.html), you can use the `create_cloud_hook` mutation. For example, to create an email Cloud Hook you'd use the following mutation:

```graphql
mutation {
  create_cloud_hook(
    input: {
      type: EMAIL,
      name: "Example",
      version_group_id: "abc",
      states: ["Running"],
      config: "{\"to\": \"test@test.com\"}"}
      ) {
    id
  }
}
```

A full list of Cloud Hook queries and mutations can be found in the API schema (for example in the [Interactive API](/orchestration/ui/interactive-api.html) page of the UI.)

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
