---
sidebarDepth: 2
editLink: false
---
# Jira Tasks
---
 ## JiraTask
 <div class='class-sig' id='prefect-tasks-jira-jira-task-jiratask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.jira.jira_task.JiraTask</p>(server_url=None, project_name=None, assignee=&quot;-1&quot;, issue_type=None, summary=None, description=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/jira/jira_task.py#L8">[source]</a></span></div>

Task for creating a jira issue. For this task to function properly, you need a Jira account and API token.  The API token can be created at: https://id.atlassian.com/manage/api-tokens The Jira account username ('JIRAUSER'), API token ('JIRATOKEN') can be set as part of a 'JIRASECRETS' object in Prefect Secrets.

An example 'JIRASECRETS' secret configuration looks like:


```toml
[secrets]
JIRASECRETS.JIRATOKEN = "XXXXXXXXX"
JIRASECRETS.JIRAUSER = "xxxxx@yyy.com"
JIRASECRETS.JIRASERVER = "https://???.atlassian.net"

```

The server URL can be set as part of the 'JIRASECRETS' object ('JIRASERVER') or passed to the task as the "server_URL" argument.

**Args**:     <ul class="args"><li class="args">`server_url (str)`: the URL of your atlassian account e.g.         "https://test.atlassian.net".  Can also be set as a Prefect Secret.     </li><li class="args">`project_name(str)`:  the key for your jira project. Can also be set at run time.     </li><li class="args">`assignee (str, optional)`: the atlassian accountId of the person you want to assign         the ticket to.  Defaults to "automatic" if this is not set. Can also be set at run         time.     </li><li class="args">`issue_type (str, optional)`: the type of issue you want to create.  Can also be set at         run time. Defaults to 'Task'.     </li><li class="args">`summary (str, optional)`: summary or title for your issue. Can also be set at run time.     </li><li class="args">`description (str, optional)`: description or additional information for the issue. Can         also be set at run time.     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the standard Task         init method.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-jira-jira-task-jiratask-run'><p class="prefect-class">prefect.tasks.jira.jira_task.JiraTask.run</p>(username=None, access_token=None, server_url=None, project_name=None, assignee=&quot;-1&quot;, issue_type=None, summary=None, description=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/jira/jira_task.py#L61">[source]</a></span></div>
<p class="methods">Run method for this Task. Invoked by calling this Task after initialization within a Flow context, or by using `Task.bind`.<br><br>**Args**:     <ul class="args"><li class="args">`username(str)`: the jira username, provided with a Prefect secret (defaults to         JIRAUSER in JIRASECRETS)     </li><li class="args">`access_token (str)`: a Jira access token, provided with a Prefect secret (defaults         to JIRATOKEN in JIRASECRETS)     </li><li class="args">`server_url (str)`: the URL of your atlassian account e.g.         "https://test.atlassian.net".  Can also be set as a Prefect Secret. Defaults to         the one provided at initialization     </li><li class="args">`project_name(str)`:  the key for your jira project; defaults to the one provided         at initialization     </li><li class="args">`assignee (str, optional)`: the atlassian accountId of the person you want to         assign the ticket to; defaults to "automatic" if this is not set; defaults to         the one provided at initialization     </li><li class="args">`issue_type (str, optional)`: the type of issue you want to create; defaults to         'Task'     </li><li class="args">`summary (str, optional)`: summary or title for your issue; defaults to the one         provided at initialization     </li><li class="args">`description (str, optional)`: description or additional information for the issue;         defaults to the one provided at initialization</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a `project_name` or 'summary' are not provided</li></ul> **Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>

 ## JiraServiceDeskTask
 <div class='class-sig' id='prefect-tasks-jira-jira-service-desk-jiraservicedesktask'><p class="prefect-sig">class </p><p class="prefect-class">prefect.tasks.jira.jira_service_desk.JiraServiceDeskTask</p>(server_url=None, service_desk_id=None, issue_type=None, summary=None, description=None, **kwargs)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/jira/jira_service_desk.py#L8">[source]</a></span></div>

Task for creating a Jira Service Desk customer request. For this task to function properly, you need a Jira account and API token.  The API token can be created at: https://id.atlassian.com/manage/api-tokens The Jira account username ('JIRAUSER'), API token ('JIRATOKEN') can be set as part of a 'JIRASECRETS' object in Prefect Secrets.

An example 'JIRASECRETS' secret configuration looks like:


```toml
[secrets]
JIRASECRETS.JIRATOKEN = "XXXXXXXXX"
JIRASECRETS.JIRAUSER = "xxxxx@yyy.com"
JIRASECRETS.JIRASERVER = "https://???.atlassian.net"

```

The server URL can be set as part of the 'JIRASECRETS' object ('JIRASERVER') or passed to the task as the "server_URL" argument.

The service desk id and issue type will show in the URL when you raise a customer request in the UI.  For example, in the below URL the service desk id is "3" and the issue_type is 10010:


```
https://test.atlassian.net/servicedesk/customer/portal/3/group/3/create/10010

````

**Args**:     <ul class="args"><li class="args">`server_url (str)`: the URL of your atlassian account e.g.         "https://test.atlassian.net".  Can also be set as a Prefect Secret.     </li><li class="args">`service_desk_id (str)`:  the id for your jira service desk. Can also be set at run time.     </li><li class="args">`issue_type (int, optional)`: the type of issue you want to create.  Can also be set at         run time.     </li><li class="args">`summary (str, optional)`: summary or title for your issue. Can also be set at run time.     </li><li class="args">`description (str, optional)`: description or additional information for the issue. Can         also be set at run time.     </li><li class="args">`**kwargs (Any, optional)`: additional keyword arguments to pass to the standard Task         init method.</li></ul>

|methods: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;|
|:----|
 | <div class='method-sig' id='prefect-tasks-jira-jira-service-desk-jiraservicedesktask-run'><p class="prefect-class">prefect.tasks.jira.jira_service_desk.JiraServiceDeskTask.run</p>(username=None, access_token=None, server_url=None, service_desk_id=None, issue_type=None, summary=None, description=None)<span class="source"><a href="https://github.com/PrefectHQ/prefect/blob/master/src/prefect/tasks/jira/jira_service_desk.py#L64">[source]</a></span></div>
<p class="methods">Run method for this Task. Invoked by calling this Task after initialization within a Flow context, or by using `Task.bind`.<br><br>**Args**:     <ul class="args"><li class="args">`username(str)`: the jira username, provided with a Prefect secret (defaults to         JIRAUSER in JIRASECRETS)     </li><li class="args">`access_token (str)`: a Jira access token, provided with a Prefect secret (defaults         to JIRATOKEN in JIRASECRETS)     </li><li class="args">`server_url (str)`: the URL of your atlassian account e.g.         "https://test.atlassian.net".  Can also be set as a Prefect Secret. Defaults to         the one provided at initialization     </li><li class="args">`service_desk_id(str)`:  the key for your jira project; defaults to the one         provided at initialization     </li><li class="args">`issue_type (str, optional)`: the type of issue you want to create;     </li><li class="args">`summary (str, optional)`: summary or title for your issue; defaults to the one         provided at initialization     </li><li class="args">`description (str, optional)`: description or additional information for the issue;         defaults to the one provided at initialization</li></ul> **Raises**:     <ul class="args"><li class="args">`ValueError`: if a `service_desk_id`, `request_type`, or `summary` are not provided</li></ul> **Returns**:     <ul class="args"><li class="args">None</li></ul></p>|

---
<br>


<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>