# Automations

Automations allow you to take actions (such as cancelling a flow run or sending a notification to certain endpoints) when your flow or agent encounters a certain event.  Current events that you can monitor are:
- A flow run enters a given state; 
- Runs from multiple (or even all) flows enter a given state;
- A Flow run fails to start after being scheduled for a certain amount of time; 
- A Flow run fails to finish after running for a certain amount of time; 
- All agents with the same agent-config-id become unhealthy. 

For example, you can send a Slack message to your team when a run from a production-critical flow has failed, along with the reason for the failure, so you can respond immediately. Or you can cancel a run that has been stuck running for more than an hour.  The Prefect backend API currently supports hooks for Slack, Twilio, Pager Duty, email, and a more general Webhook.

You can set up and edit your Automations using the [API](/orchestration/concepts/api.html) or the Automations page in the UI.


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