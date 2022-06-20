<p align="center">
   <img src="https://www.prefect.io/assets/img/prefect-logo-gradient-navy.0cb04f87.svg" width="500" style="max-width: 500px;">
</p>

<p align="center">
<a href=https://circleci.com/gh/PrefectHQ/prefect/tree/master>
    <img src="https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=shield&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344">
</a>

<a href=https://github.com/ambv/black>
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg">
</a>

<a href="https://pypi.org/project/prefect/">
    <img src="https://static.pepy.tech/badge/prefect/month">
</a>

<a href="https://hub.docker.com/r/prefecthq/prefect">
    <img src="https://img.shields.io/docker/pulls/prefecthq/prefect.svg?color=%2327B1FF&logoColor=%234D606E">
</a>

<a href="https://www.prefect.io/slack/">
    <img src="https://img.shields.io/static/v1.svg?label=chat&message=on%20slack&color=27b1ff&style=flat">
</a>


<a href="https://discourse.prefect.io/">
    <img src="https://img.shields.io/static/v1.svg?label=chat&message=on%20discourse&color=27b1ff&style=flat">
</a>


</p>

## Hello, world! 👋

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](https://docs.prefect.io); get the [code](#installation); ask us [anything](https://www.prefect.io/slack); chat with the community via [Prefect Discourse](https://discourse.prefect.io/)!

### Welcome to Workflows

Prefect's Pythonic API should feel familiar for newcomers. Mark functions as tasks and call them on each other to build up a flow.

```python
from prefect import task, Flow, Parameter


@task(log_stdout=True)
def say_hello(name):
    print("Hello, {}!".format(name))


with Flow("My First Flow") as flow:
    name = Parameter('name')
    say_hello(name)


flow.run(name='world') # "Hello, world!"
flow.run(name='Marvin') # "Hello, Marvin!"
```

For more detail, please see the [Core docs](https://docs.prefect.io/core/)

### UI and Server

<p align="center" style="margin-bottom:40px;">
<img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/orchestration/ui/dashboard-overview2.png"  height=440 style="max-height: 440px;">
</p>

In addition to the [Prefect Cloud](https://www.prefect.io/cloud) platform, Prefect includes an open-source backend for orchestrating and managing flows, consisting primarily of [Prefect Server](https://github.com/prefecthq/server) and [Prefect UI](https://github.com/prefecthq/ui). This local server stores flow metadata in a Postgres database and exposes a GraphQL API.

By default, Prefect is configured to use Prefect Cloud as the backend, and you can set Prefect Cloud as the backend by running the command: 

```bash
$ prefect backend cloud
```

To use Prefect Server as the backend, run the following command to configure Prefect for local orchestration:

```bash
$ prefect backend server
``` 

Please note the server requires [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/) to be running.

To start the server, UI, and all required infrastructure, run:

```bash
$ prefect server start
```

Once all components are running, you can view the UI by visiting [http://localhost:8080](http://localhost:8080).

**Tip:** Check our [troubleshooting guide](https://docs.prefect.io/orchestration/server/troubleshooting.html) if you run into any issues starting the server.


Please note that executing flows from the server requires at least one Prefect Agent to be running. For example, to start the local Agent, run the following command: 

```bash
$ prefect agent local start
```

Finally, to [register any flow](https://docs.prefect.io/orchestration/concepts/flows.html#registration) with the server, call `flow.register(project_name="<project_name>")` within your flow using the name of your project. For more detail, please see the [orchestration docs](https://docs.prefect.io/orchestration/).

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and makes sure that the rules are followed. Similarly, Prefect is responsible for making sure that workflows execute properly.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Integrations

Thanks to Prefect's growing task library and deep ecosystem integrations, building data applications is easier than ever.

Something missing? Open a [feature request](https://github.com/PrefectHQ/prefect/issues/new/choose) or [contribute a PR](https://docs.prefect.io/core/development/overview.html)! Prefect was designed to make adding new functionality extremely easy, whether you build on top of the open-source package or maintain an internal task library for your team.

### Task Library

The Prefect task library is a constantly growing list of pre-defined tasks that provide off-the-shelf functionality for working with a wide range of tools anywhere from shell script execution to Kubernetes job management to sending tweets.

<table>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/airbyte.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/airbyte.html">Airbyte</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/airtable.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/airtable.html">Airtable</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/asana_logo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/asana.html">Asana</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/aws.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/aws.html">AWS</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/azure.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/azure.html">Azure</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/azure_ml.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/azureml.html">Azure ML</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/census.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/census.html">Census</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/cubejs.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/cubejs.html">CubeJS</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/databricks.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/databricks.html">Databricks</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dbt.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/dbt.html">dbt</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/docker.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/docker.html">Docker</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dremio.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/dremio.html">Dremio</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dropbox.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/dropbox.html">Dropbox</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/email.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/notifications.html#emailtask">Email</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/firebolt.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/firebolt.html">Firebolt</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/fivetran.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/fivetran.html">Fivetran</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/github.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/github.html">GitHub</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/google_cloud.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/gcp.html">Google Cloud</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/sheets.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/gsheets.html">Google Sheets</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/ge.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/great_expectations.html">Great Expectations</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/jira.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/jira.html">Jira</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/jupyter.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/jupyter.html">Jupyter</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/kubernetes.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/kubernetes.html">Kubernetes</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/mixpanel.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/mixpanel.html">Mixpanel</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/monday.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/monday.html">Monday</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/monte_carlo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/monte_carlo.html">Monte Carlo</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/mysql.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/mysql.html">MySQL</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/postgres.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/postgres.html">PostgreSQL</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/prometheus.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/prometheus.html">Prometheus</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/pushbullet.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/notifications.html#pushbullettask">Pushbullet</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/python.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/function.html">Python</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/redis.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/redis.html">Redis</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/rlogo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/rss.html">RSS</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/sendgrid.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/sendgrid.html">SendGrid</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/shell.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/shell.html">Shell</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/slack.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/notifications.html#slacktask">Slack</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/snowflake.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/snowflake.html">Snowflake</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/spacy.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/spacy.html">spaCy</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/sqlserverlogo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/sql_server.html">SQL Server</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/sqlite.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/sqlite.html">SQLite</a></td>
  </tr>
  <tr>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/assets/verified_logo.png"><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/transform.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/transform.html">Transform</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/trello.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/trello.html">Trello</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/tlogo.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/twitter.html">Twitter</a></td>
    <td><img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/zendesk.png" height="128" width="128" style="max-height: 128px; max-width: 128px;"><a href="https://docs.prefect.io/api/latest/tasks/zendesk.html">Zendesk</a></td>
    <td></td>
  </tr>
</table>

### Deployment & Execution

| &nbsp; | &nbsp; | &nbsp; | &nbsp; | &nbsp; |
| ------ | ------ | ------ | ------ | ------ |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/azure.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Azure</p>](https://azure.microsoft.com/en-us/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/aws.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>AWS</p>](https://aws.amazon.com/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dask.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Dask</p>](https://dask.org/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/docker.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Docker</p>](https://www.docker.com/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/google_cloud.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Google Cloud</p>](https://cloud.google.com/)                                                          |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/kubernetes.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Kubernetes</p>](https://kubernetes.io/)   |                                                                                                                                                                                                                    |                                                                                                                                                                                                                |                                                                                                                                                                                                                          | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/shell.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Universal Deploy</p>](https://medium.com/the-prefect-blog/introducing-prefect-universal-deploy-7992283e5911) |

## Resources

Prefect provides a variety of resources to help guide you to a successful outcome.

We are committed to ensuring a positive environment, and all interactions are governed by our [Code of Conduct](https://docs.prefect.io/core/code_of_conduct.html).

### Documentation

Prefect's documentation -- including concepts, tutorials, and a full API reference -- is always available at [docs.prefect.io](https://docs.prefect.io).

Instructions for contributing to documentation can be found in the [development guide](https://docs.prefect.io/core/development/documentation.html).

### Prefect Discourse

Join our [forum](https://discourse.prefect.io/) to share knowledge, discuss ideas, find answers to common questions and get support.

### Slack Community

Join our [Slack](https://www.prefect.io/slack) to chat about Prefect, ask questions, and share tips.

### Blog

Visit the [Prefect Blog](https://medium.com/the-prefect-blog) for updates and insights from the Prefect team.

### Support

Prefect offers a variety of community and premium [support options](https://www.prefect.io/support) for users of both Prefect Core and Prefect Cloud.

### Contributing

Read about Prefect's [community](https://docs.prefect.io/core/community.html) or dive in to the [development guides](https://docs.prefect.io/core/development/overview.html) for information about contributions, documentation, code style, and testing.

## Installation

### Requirements

Prefect requires Python 3.7+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

### Latest Release

To install Prefect, run:

```bash
pip install prefect
```

or, if you prefer to use `conda`:

```bash
conda install -c conda-forge prefect
```

or `pipenv`:

```bash
pipenv install --pre prefect
```

### Bleeding Edge

For development or just to try out the latest features, you may want to install Prefect directly from source.

Please note that the master branch of Prefect is not guaranteed to be compatible with Prefect Cloud or the local server.

```bash
git clone https://github.com/PrefectHQ/prefect.git
pip install ./prefect
```

## License

Prefect Core is licensed under the [Apache Software License Version 2.0](https://www.apache.org/licenses/LICENSE-2.0). Please note that Prefect Core includes utilities for running [Prefect Server](https://www.github.com/prefecthq/server) and the [Prefect UI](https://www.github.com/prefecthq/ui), which are themselves licensed under the [Prefect Community License](https://www.prefect.io/legal/prefect-community-license).
