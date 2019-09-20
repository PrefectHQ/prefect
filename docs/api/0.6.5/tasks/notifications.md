---
sidebarDepth: 2
editLink: false
---
# Notification Tasks
---
Collection of tasks for sending notifications.

Useful for situations in which state handlers are inappropriate.
 ## EmailTask
 <div class='class-sig' id='prefect-tasks-notifications-email-task-emailtask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.notifications.email_task.EmailTask</p>(subject=None, msg=None, email_to=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/email_task.py#L12">[source]</a></span></div>

Task for sending email from an authenticated Gmail address.  For this task to function properly, you must have the `"EMAIL_USERNAME"` and `"EMAIL_PASSWORD"` Prefect Secrets set.  It is recommended you use a [Google App Password](https://support.google.com/accounts/answer/185833) for this purpose.

**Args**:     <ul class="args"><li class="args">`subject (str, optional)`: the subject of the email; can also be provided at runtime     </li><li class="args">`msg (str, optional)`: the contents of the email; can also be provided at runtime     </li><li class="args">`email_to (str, optional)`: the destination email address to send the message to; can also         be provided at runtime     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the base Task initialization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-notifications-email-task-emailtask-run'><p class="prefect-class">prefect.tasks.notifications.email_task.EmailTask.run</p>(subject=None, msg=None, email_to=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/email_task.py#L34">[source]</a></span></div>
<p class="methods">Run method which sends an email.<br><br>**Args**:     <ul class="args"><li class="args">`subject (str, optional)`: the subject of the email; defaults to the one provided         at initialization     </li><li class="args">`msg (str, optional)`: the contents of the email; defaults to the one provided         at initialization     </li><li class="args">`email_to (str, optional)`: the destination email address to send the message to;         defaults to the one provided at initialization</li></ul>**Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>

 ## SlackTask
 <div class='class-sig' id='prefect-tasks-notifications-slack-task-slacktask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.notifications.slack_task.SlackTask</p>(message=None, webhook_secret="SLACK_WEBHOOK_URL", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/slack_task.py#L10">[source]</a></span></div>

Task for sending a message via Slack.  For this task to function properly, you must have a Prefect Secret set which stores your Slack webhook URL.  For installing the Prefect App, please see these [installation instructions](https://docs.prefect.io/core/tutorials/slack-notifications.html#installation-instructions).

**Args**:     <ul class="args"><li class="args">`message (str, optional)`: the message to send; can also be provided at runtime     </li><li class="args">`webhook_secret (str, optional)`: the name of the Prefect Secret which stores your slack webhook URL;         defaults to `"SLACK_WEBHOOK_URL"`     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the base Task initialization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-notifications-slack-task-slacktask-run'><p class="prefect-class">prefect.tasks.notifications.slack_task.SlackTask.run</p>(message=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/slack_task.py#L33">[source]</a></span></div>
<p class="methods">Run method which sends a Slack message.<br><br>**Args**:     <ul class="args"><li class="args">`message (str, optional)`: the message to send; if not provided here, will use the value provided         at initialization</li></ul>**Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on September 20, 2019 at 19:42 UTC</p>