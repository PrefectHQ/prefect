---
sidebarDepth: 2
editLink: false
---
# Notification Tasks
---
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


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>by Prefect 0.5.0 on March 29, 2019 at 17:39 UTC</p>
