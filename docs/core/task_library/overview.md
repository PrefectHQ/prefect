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

|                                                                                                                                                                                           |                                                                                                                                                                               |                                                                                                                                                                                      |                                                                                                                                                                                                     |                                                                                                                                                                                |
|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <img src="/logos/airtable.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Airtable</p>](https://docs.prefect.io/api/latest/tasks/airtable.html)               | <img src="/logos/asana_logo.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Asana</p>](https://docs.prefect.io/api/latest/tasks/asana.html)       | <img src="/logos/aws.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>AWS</p>](https://docs.prefect.io/api/latest/tasks/aws.html)                         | <img src="/logos/azure.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Azure</p>](https://docs.prefect.io/api/latest/tasks/azure.html)                                  | <img src="/logos/azure_ml.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Azure ML</p>](https://docs.prefect.io/api/latest/tasks/azureml.html)     |
| <img src="/logos/databricks.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Databricks</p>](https://docs.prefect.io/api/latest/tasks/databricks.html)         | <img src="/logos/dbt.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>DBT</p>](https://docs.prefect.io/api/latest/tasks/dbt.html)                  | <img src="/logos/docker.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Docker</p>](https://docs.prefect.io/api/latest/tasks/docker.html)                | <img src="/logos/dremio.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Dremio</p>](https://docs.prefect.io/api/latest/tasks/dremio.html)                               | <img src="/logos/dropbox.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Dropbox</p>](https://docs.prefect.io/api/latest/tasks/dropbox.html)       |
| <img src="/logos/email.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Email</p>](https://docs.prefect.io/api/latest/tasks/notifications.html#emailtask)      | <img src="/logos/github.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>GitHub</p>](https://docs.prefect.io/api/latest/tasks/github.html)         | <img src="/logos/fivetran.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Fivetran</p>](https://docs.prefect.io/api/latest/tasks/fivetran.html)          | <img src="/logos/google_cloud.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Google Cloud</p>](https://docs.prefect.io/api/latest/tasks/gcp.html)                      | <img src="/logos/sheets.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Google Sheets</p>](https://docs.prefect.io/api/latest/tasks/gsheets.html)  |
| <img src="/logos/ge.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Great Expectations</p>](https://docs.prefect.io/api/latest/tasks/great_expectations.html) | <img src="/logos/jira.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Jira</p>](https://docs.prefect.io/api/latest/tasks/jira.html)               | <img src="/logos/jupyter.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Jupyter</p>](https://docs.prefect.io/api/latest/tasks/jupyter.html)             | <img src="/logos/kubernetes.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Kubernetes</p>](https://docs.prefect.io/api/latest/tasks/kubernetes.html)                   | <img src="/logos/monday.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Monday</p>](https://docs.prefect.io/api/latest/tasks/monday.html)          |
| <img src="/logos/mysql.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>MySQL</p>](https://docs.prefect.io/api/latest/tasks/mysql.html)                        | <img src="/logos/postgres.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>PostgreSQL</p>](https://docs.prefect.io/api/latest/tasks/postgres.html) | <img src="/logos/prometheus.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Prometheus</p>](https://docs.prefect.io/api/latest/tasks/prometheus.html) | <img src="/logos/python.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Python</p>](https://docs.prefect.io/api/latest/tasks/function.html)              | <img src="/logos/pushbullet.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Pushbullet</p>](https://docs.prefect.io/api/latest/tasks/notifications.html#pushbullettask) | <img src="/logos/redis.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Redis</p>](https://docs.prefect.io/api/latest/tasks/redis.html)             |
| <img src="/logos/rlogo.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>RSS</p>](https://docs.prefect.io/api/latest/tasks/rss.html)                            | <img src="/logos/sendgrid.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>SendGrid</p>](https://docs.prefect.io/api/latest/tasks/sendgrid.html)   | <img src="/logos/shell.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Shell</p>](https://docs.prefect.io/api/latest/tasks/shell.html)                   | <img src="/logos/slack.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Slack</p>](https://docs.prefect.io/api/latest/tasks/notifications.html#slacktask)                | <img src="/logos/snowflake.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Snowflake</p>](https://docs.prefect.io/api/latest/tasks/snowflake.html) |
| <img src="/logos/spacy.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>SpaCy</p>](https://docs.prefect.io/api/latest/tasks/spacy.html)                        | <img src="/logos/sqlite.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>SQLite</p>](https://docs.prefect.io/api/latest/tasks/sqlite.html)         | <img src="/logos/sqlserverlogo.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>SQL Server</p>](https://docs.prefect.io/api/latest/tasks/sql_server.html) | <img src="/logos/trello.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Trello</p>](https://docs.prefect.io/api/latest/tasks/trello.html)                               | <img src="/logos/tlogo.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Twitter</p>](https://docs.prefect.io/api/latest/tasks/twitter.html)         |

## Task library in action

Just like any other Prefect [task](/core/concepts/tasks.html), tasks in the task library can be
used by importing and adding them to your flow.

:::: tabs
::: tab Functional API
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
:::

::: tab Imperative API
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
:::
::::

Keyword arguments for tasks imported from the task library can either be set at initialization for reuse
purposed or optionally set and overwritten when defining the flow.

:::: tabs
::: tab Functional API
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
:::

::: tab Imperative API
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
:::
::::

For more information on the tasks available for use in the task library visit the API
[reference documentation](/api/latest) for the `prefect.tasks` and if you are interested in contributing to the task library visit the [contributing page](/core/task_library/contributing.html)!
