# Overview

The Prefect task library is a constantly growing list of pre-defined tasks that provide off-the-shelf
functionality for working with a wide range of tools anywhere from shell script execution to kubernetes
job management to sending tweets. A majority of the task library is community supported and thus opens
the door for users who want to contribute tasks for working with any number of tools. Tasks in the task
library are created with a specific goal in mind such as creating a Kubernetes job with
[`CreateNamespacedJob`](/api/latest/tasks/kubernetes.html#createnamespacedjob) or invoking an AWS lambda
function with [`LambdaInvoke`](/api/latest/tasks/aws.html#lambdainvoke).

Below is a table showcasing some of the tasks that have been contributed to the task library for
interfacing with varying tools and services that users have deemed useful. For a full list of tasks in
the library and more information on how to use them visit the API [reference documentation](/api/latest)
for the `prefect.tasks` module.

Tasks marked with the <Badge text="Verified" type="success" vertical="middle"></Badge> badge have been reviewed and approved by Prefect.

<ClientOnly>
<table>
  <tr>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/airbyte.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/airbyte.html">Airbyte</a></td>
    <td><img src="/logos/airtable.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/airtable.html">Airtable</a></td>
    <td><img src="/logos/asana_logo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/asana.html">Asana</a></td>
    <td><img src="/logos/aws.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/aws.html">AWS</a></td>
    <td><img src="/logos/azure.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/azure.html">Azure</a></td>
  </tr>
  <tr>
    <td><img src="/logos/azure_ml.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/azureml.html">Azure ML</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/census.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/census.html">Census</a></td>
    <td><img src="/logos/cubejs.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/cubejs.html">CubeJS</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/databricks.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/databricks.html">Databricks</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/dbt.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/dbt.html">dbt</a></td>
  </tr>
  <tr>
    <td><img src="/logos/docker.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/docker.html">Docker</a></td>
    <td><img src="/logos/dremio.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/dremio.html">Dremio</a></td>
    <td><img src="/logos/dropbox.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/dropbox.html">Dropbox</a></td>
    <td><img src="/logos/email.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/notifications.html#emailtask">Email</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/firebolt.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/firebolt.html">Firebolt</a></td>
  </tr>
  <tr>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/fivetran.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/fivetran.html">Fivetran</a></td>
    <td><img src="/logos/github.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/github.html">GitHub</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/google_cloud.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/gcp.html">Google Cloud</a></td>
    <td><img src="/logos/sheets.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/gsheets.html">Google Sheets</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/ge.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/great_expectations.html">Great Expectations</a></td>
  </tr>
  <tr>
    <td><img src="/logos/jira.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/jira.html">Jira</a></td>
    <td><img src="/logos/jupyter.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/jupyter.html">Jupyter</a></td>
    <td><img src="/logos/kubernetes.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/kubernetes.html">Kubernetes</a></td>
    <td><img src="/logos/mixpanel.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/mixpanel.html">Mixpanel</a></td>
    <td><img src="/logos/monday.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/monday.html">Monday</a></td>
  </tr>
  <tr>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/monte_carlo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/monte_carlo.html">Monte Carlo</a></td>
    <td><img src="/logos/mysql.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/mysql.html">MySQL</a></td>
    <td><img src="/logos/postgres.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/postgres.html">PostgreSQL</a></td>
    <td><img src="/logos/prometheus.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/prometheus.html">Prometheus</a></td>
    <td><img src="/logos/pushbullet.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/notifications.html#pushbullettask">Pushbullet</a></td>
  </tr>
  <tr>
    <td><img src="/logos/python.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/function.html">Python</a></td>
    <td><img src="/logos/redis.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/redis.html">Redis</a></td>
    <td><img src="/logos/rlogo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/rss.html">RSS</a></td>
    <td><img src="/logos/sendgrid.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/sendgrid.html">SendGrid</a></td>
    <td><img src="/logos/shell.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/shell.html">Shell</a></td>
  </tr>
  <tr>
    <td><img src="/logos/slack.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/notifications.html#slacktask">Slack</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/snowflake.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/snowflake.html">Snowflake</a></td>
    <td><img src="/logos/spacy.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/spacy.html">spaCy</a></td>
    <td><img src="/logos/sqlserverlogo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/sql_server.html">SQL Server</a></td>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/sqlite.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/sqlite.html">SQLite</a></td>
  </tr>
  <tr>
    <td><Badge text="Verified" type="success"></Badge><img src="/logos/transform.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/transform.html">Transform</a></td>
    <td><img src="/logos/trello.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/trello.html">Trello</a></td>
    <td><img src="/logos/tlogo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/twitter.html">Twitter</a></td>
    <td><img src="/logos/zendesk.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/zendesk.html">Zendesk</a></td>
    <td></td>
  </tr>
</table>
</ClientOnly>

## Task library in action

Just like any other Prefect [task](/core/concepts/tasks.html), tasks in the task library can be
used by importing and adding them to your flow.

Functional API:

```python
from prefect import task, Flow
from prefect.tasks.shell import ShellTask

ls_task = ShellTask(command="ls", return_all=True)

@task
def show_output(std_out):
    print(std_out)

with Flow("list_files") as flow:
    ls = ls_task()
    show_output(ls)
```

Imperative API:

```python
from prefect import Task, Flow
from prefect.tasks.shell import ShellTask

class ShowOutput(Task):
    def run(self, std_out):
        print(std_out)

ls_task = ShellTask(command="ls", return_all=True)
show_output = ShowOutput()

flow = Flow("list_files")
show_output.set_upstream(ls_task, key="std_out", flow=flow)
```


Keyword arguments for tasks imported from the task library can either be set at initialization for reuse
purposed or optionally set and overwritten when defining the flow.

Functional API:

```python
from prefect import task, Flow
from prefect.tasks.shell import ShellTask

# Will only return the listed files
ls_task = ShellTask(command="ls", return_all=True)

@task
def show_output(std_out):
    print(std_out)

with Flow("count_files") as flow:
    ls = ls_task()
    show_output(ls)

    # Override command to count listed files
    ls_count = ls_task(command="ls | wc -l")
    show_output(ls_count)
```

Imperative API:

```python
from prefect import Task, Flow
from prefect.tasks.shell import ShellTask

class ShowOutput(Task):
    def run(self, std_out):
        print(std_out)

ls_task = ShellTask(command="ls", return_all=True)
show_output = ShowOutput()

ls_count = ShellTask(command="ls | wc -l", return_all=True)
show_output2 = ShowOutput()

flow = Flow("count_files")
show_output.set_upstream(ls_task, key="std_out", flow=flow)
show_output2.set_upstream(ls_count, key="std_out", flow=flow)
```


For more information on the tasks available for use in the task library visit the API
[reference documentation](/api/latest) for the `prefect.tasks` and if you are interested in contributing to the task library visit the [contributing page](/core/task_library/contributing.html)!
