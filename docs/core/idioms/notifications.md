# Configuring notifications

Sending notifications based on events in Prefect is a common pattern. Types of notifications generally include functionality such as posting state of runs to Slack, sending a text message on failure, etc. There are many places in Prefect to hook in notification systems and this idiom will go over three possibilities.

### Downstream tasks

Adding tasks to your flow that respond to upstream events is one way of sending notifications. These tasks can be built in any way you would like and the Prefect task library even ships with a few [notification tasks](/api/latest/tasks/notifications.html)! Below is an example of using the [`SlackTask`](/api/latest/tasks/notifications.html#slacktask) to send a notification to Slack.

::: warning Slack Webhook URL
This code below makes use of a [Slack Webhook URL](https://api.slack.com/messaging/webhooks) as a Prefect Secret. For more information on using Prefect Secrets visit the [concept documentation](/core/concepts/secrets.html).
:::

:::: tabs
::: tab Functional API
```python
from prefect import task, Flow
from prefect.tasks.notifications import SlackTask

@task
def get_value():
    return "Test SlackTask!"

slack_task = SlackTask()

with Flow("slack-test") as flow:
    value = get_value()
    slack_task(message=value)
```
:::

::: tab Imperative API
```python
from prefect import Task, Flow
from prefect.tasks.notifications import SlackTask

class GetValue(Task):
    def run(self):
        return "Test SlackTask!"

flow = Flow("slack-test")

value = GetValue()
slack_task = SlackTask()

slack_task.set_upstream(value, key="message", flow=flow)
```
:::
::::

In this example the `SlackTask` notification will execute every time the upstream task is successful. To enable a different behavior where this task runs due to different upstream task states attach a [trigger](/api/latest/triggers.html#triggers) to the task. For example, you could execute this task in certain situations such as upstream failures using an `any_failed` trigger.

### State handlers

Another common pattern for sending notifications is through [state handlers](/core/concepts/notifications.html#state-handlers). State handlers are a way of reacting to specific state changes on a task and Prefect ships with a [few state handlers](/api/latest/utilities/notifications.html) for working with different services. Outside of those default handlers it is straightforward to make completely custom handlers! State handlers can be set on individual tasks and on entire flows. This means that you can receive notifications for both task state changes as well as state changes for the flow. For more information on this take a look at the relevant [concept documentation](/core/concepts/notifications.html).

### Cloud hooks <Badge text="Cloud"/>

Users of Prefect Cloud have access to something called Cloud Hooks which is a way of configuring notifications based on state changes without having to write any code for the tasks or flow itself. Cloud Hooks are the only *guaranteed* way of getting notifications because they have no reliance on your code and are managed entirely on the Prefect Cloud side. For more information on Cloud Hooks visit the [documentation](/orchestration/concepts/cloud_hooks.html).
