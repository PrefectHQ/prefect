---
description: Configure notifications based on flow state from the Prefect UI and Prefect Cloud.
tags:
    - Orion
    - UI
    - states
    - flow runs
    - notifications
    - alerts
    - Prefect Cloud
---

# Notifications

At any time, you can visit the [Prefect UI](/ui/flow-runs/) to get a comprehensive view of the state of all of your flows, but when something goes wrong with one of your flows, you need that information immediately. 

Notifications enable you to set up alerts that are sent when a flow enters any state you specify. When your flow and task runs changes [state](/concepts/states/), Prefect notes the state change and checks whether the new state matches any notification policies. If it does, a new notification is queued.

Currently Prefect 2 supports sending notifications via:

- Slack message to a channel
- Microsoft Teams message to a channel
- PagerDuty to alerts
- Twilio to phone numbers
- Email (Prefect Cloud only)

To configure a notification, go to the **Notifications** page and select **Create Notification** or the **+** button. 

![Creating a notification in the Prefect UI](/img/ui/orion-create-slack-notification.png)

Notifications are structured just as you would describe them to someone. You can choose:

- Which run states should trigger a notification.
- Tags to filter which flow runs are covered by the notification.
- Whether to send an email, a Slack message, Microsoft Teams message, or other services.

For Slack notifications, the configuration requires webhook credentials for your Slack and the channel to which the message is sent.

For email notifications (supported on Prefect Cloud only), the configuraiton requires email addresses to which the message is sent.

For example, to get a Slack message if a flow with a `daily-etl` tag fails, the notification will read:

> If a run of any flow with **daily-etl** tag enters a **failed** state, send a notification to **my-slack-webhook**

When the conditions of the notification are triggered, you’ll receive a simple message:

> The **fuzzy-leopard** run of the **daily-etl** flow entered a **failed** state at **22-06-27 16:21:37 EST**.

On the **Notifications** page you can pause, edit, or delete any configured notification.

![Viewing all configured notification in the Prefect UI](/img/ui/orion-notifications.png)
