---
sidebarDepth: 2
editLink: false
---
# Notification Tasks
---
Collection of tasks for sending notifications.

Useful for situations in which state handlers are inappropriate.
 ## EmailTask
 <div class='class-sig' id='prefect-tasks-notifications-email-task-emailtask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.notifications.email_task.EmailTask</p>(subject=None, msg=None, email_to=None, email_from="notifications@prefect.io", smtp_server="smtp.gmail.com", smtp_port=465, smtp_type="SSL", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/email_task.py#L12">[source]</a></span></div>

Task for sending email from an authenticated email service over SMTP. For this task to function properly, you must have the `"EMAIL_USERNAME"` and `"EMAIL_PASSWORD"` Prefect Secrets set.  It is recommended you use a [Google App Password](https://support.google.com/accounts/answer/185833) if you use Gmail. The default SMTP server is set to the Gmail SMTP server on port 465 (SMTP-over-SSL)

**Args**:     <ul class="args"><li class="args">`subject (str, optional)`: the subject of the email; can also be provided at runtime     </li><li class="args">`msg (str, optional)`: the contents of the email; can also be provided at runtime     </li><li class="args">`email_to (str, optional)`: the destination email address to send the message to; can also         be provided at runtime     </li><li class="args">`email_from (str, optional)`: the email address to send from; defaults to notifications@prefect.io     </li><li class="args">`smtp_server (str, optional)`: the hostname of the SMTP server; defaults to smtp.gmail.com     </li><li class="args">`smtp_port (int, optional)`: the port number of the SMTP server; defaults to 465     </li><li class="args">`smtp_type (str, optional)`: either SSL or STARTTLS; defaults to SSL     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the base Task initialization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-notifications-email-task-emailtask-run'><p class="prefect-class">prefect.tasks.notifications.email_task.EmailTask.run</p>(subject=None, msg=None, email_to=None, email_from=None, smtp_server=None, smtp_port=None, smtp_type=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/email_task.py#L51">[source]</a></span></div>
<p class="methods">Run method which sends an email.<br><br>**Args**:     <ul class="args"><li class="args">`subject (str, optional)`: the subject of the email; defaults to the one provided         at initialization     </li><li class="args">`msg (str, optional)`: the contents of the email; defaults to the one provided         at initialization     </li><li class="args">`email_to (str, optional)`: the destination email address to send the message to;         defaults to the one provided at initialization     </li><li class="args">`email_from (str, optional)`: the email address to send from; defaults to the one         provided at initialization     </li><li class="args">`smtp_server (str, optional)`: the hostname of the SMTP server; defaults to the one         provided at initialization     </li><li class="args">`smtp_port (int, optional)`: the port number of the SMTP server; defaults to the one         provided at initialization     </li><li class="args">`smtp_type (str, optional)`: either SSL or STARTTLS; defaults to the one provided         at initialization</li></ul>**Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>

 ## SlackTask
 <div class='class-sig' id='prefect-tasks-notifications-slack-task-slacktask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.notifications.slack_task.SlackTask</p>(message=None, webhook_secret="SLACK_WEBHOOK_URL", **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/slack_task.py#L8">[source]</a></span></div>

Task for sending a message via Slack.  For this task to function properly, you must have a Prefect Secret set which stores your Slack webhook URL.  For installing the Prefect App, please see these [installation instructions](https://docs.prefect.io/core/advanced_tutorials/slack-notifications.html#installation-instructions).

**Args**:     <ul class="args"><li class="args">`message (str, optional)`: the message to send; can also be provided at runtime     </li><li class="args">`webhook_secret (str, optional)`: the name of the Prefect Secret which stores your slack webhook URL;         defaults to `"SLACK_WEBHOOK_URL"`     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the base Task initialization</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-notifications-slack-task-slacktask-run'><p class="prefect-class">prefect.tasks.notifications.slack_task.SlackTask.run</p>(message=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/slack_task.py#L31">[source]</a></span></div>
<p class="methods">Run method which sends a Slack message.<br><br>**Args**:     <ul class="args"><li class="args">`message (str, optional)`: the message to send; if not provided here, will use the value provided         at initialization</li></ul>**Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>

 ## PushbulletTask
 <div class='class-sig' id='prefect-tasks-notifications-pushbullet-task-pushbullettask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.notifications.pushbullet_task.PushbulletTask</p>(msg=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/pushbullet_task.py#L12">[source]</a></span></div>

Task for sending a notification to a mobile phone (or other device) using pushbullet. For this task to function properly, you must have the `"PUSHBULLET_TOKEN"` Prefect Secret set. You can set up a pushbullet account and/or get a token here: https://www.pushbullet.com/#settings/account

**Args**:     <ul class="args"><li class="args">`msg(str, optional)`:  The message you want to send to your phone; can also be provided at runtime.     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the standard Task init method</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-notifications-pushbullet-task-pushbullettask-run'><p class="prefect-class">prefect.tasks.notifications.pushbullet_task.PushbulletTask.run</p>(msg=None, access_token=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/notifications/pushbullet_task.py#L26">[source]</a></span></div>
<p class="methods">Run method for this Task. Invoked by calling this Task after initialization within a Flow context, or by using `Task.bind`.<br><br>**Args**:     <ul class="args"><li class="args">`msg (str)`: The message you want sent to your phone; defaults to the one provided         at initialization     </li><li class="args">`access_token (str)`: a Pushbullet access token, provided with a Prefect secret. Defaults to the "PUSHBULLET_TOKEN" secret</li></ul>**Raises**:     <ul class="args"><li class="args">None</li></ul><br><br>**Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on May 14, 2020 at 21:12 UTC</p>