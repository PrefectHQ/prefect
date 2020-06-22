<p align="center" style="margin-bottom:40px;">
<img src="https://uploads-ssl.webflow.com/5ba446b0e783e26d5a2f2382/5c942c9ca934ec5c88588297_primary-color-vertical.svg"  height=350 style="max-height: 350px;">
</p>

<p align="center">
<a href=https://circleci.com/gh/PrefectHQ/prefect/tree/master>
    <img src="https://circleci.com/gh/PrefectHQ/prefect/tree/master.svg?style=shield&circle-token=28689a55edc3c373486aaa5f11a1af3e5fc53344">
</a>

<a href="https://codecov.io/gh/PrefectHQ/prefect">
  <img src="https://codecov.io/gh/PrefectHQ/prefect/branch/master/graph/badge.svg" />
</a>

<a href=https://github.com/ambv/black>
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg">
</a>

<a href="https://pypi.org/project/prefect/">
    <img src="https://img.shields.io/pypi/dm/prefect.svg?color=%2327B1FF&label=installs&logoColor=%234D606E">
</a>

<a href="https://hub.docker.com/r/prefecthq/prefect">
    <img src="https://img.shields.io/docker/pulls/prefecthq/prefect.svg?color=%2327B1FF&logoColor=%234D606E">
</a>

<a href="https://join.slack.com/t/prefect-community/shared_invite/enQtODQ3MTA2MjI4OTgyLTliYjEyYzljNTc2OThlMDE4YmViYzk3NDU4Y2EzMWZiODM0NmU3NjM0NjIyNWY0MGIxOGQzODMxNDMxYWYyOTE">
    <img src="https://prefect-slackin.herokuapp.com/badge.svg">
</a>

</p>

## Hello, world! 👋

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](https://docs.prefect.io); get the [code](#installation); ask us [anything](https://join.slack.com/t/prefect-community/shared_invite/enQtODQ3MTA2MjI4OTgyLTliYjEyYzljNTc2OThlMDE4YmViYzk3NDU4Y2EzMWZiODM0NmU3NjM0NjIyNWY0MGIxOGQzODMxNDMxYWYyOTE)!

Have a few minutes to help make Prefect even better? Take our [feedback survey](https://forms.gle/yLWF2zR3L7TgAAxP7)!

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
<img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/orchestration/ui/dashboard-overview.png"  height=440 style="max-height: 440px;">
</p>

In addition to the [Prefect Cloud](https://www.prefect.io/cloud) platform, Prefect includes an open-source server and UI for orchestrating and managing flows. The local server stores flow metadata in a Postgres database and exposes a GraphQL API.

Before running the server for the first time, run `prefect backend server` to configure Prefect for local orchestration. Please note the server requires [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/) to be running.

To start the server, UI, and all required infrastructure, run:

```
prefect server start
```

Once all components are running, you can view the UI by visiting [http://localhost:8080](http://localhost:8080).

Please note that executing flows from the server requires at least one Prefect Agent to be running: `prefect agent start`.

Finally, to register any flow with the server, call `flow.register()`. For more detail, please see the [orchestration docs](https://docs.prefect.io/orchestration/).

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and makes sure that the rules are followed. Similarly, Prefect is responsible for making sure that workflows execute properly.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Integrations

Thanks to Prefect's growing task library and deep ecosystem integrations, building data applications is easier than ever.

Something missing? Open a [feature request](https://github.com/PrefectHQ/prefect/issues/new/choose) or [contribute a PR](https://docs.prefect.io/core/development/overview.html)! Prefect was designed to make adding new functionality extremely easy, whether you build on top of the open-source package or maintain an internal task library for your team.

### Task Library

|       |       |       |       |       |
| :---: | :---: | :---: | :---: | :---: |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/airtable.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Airtable</p>](https://docs.prefect.io/core/task_library/airtable.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/aws.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>AWS</p>](https://docs.prefect.io/core/task_library/aws.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/azure.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Azure</p>](https://docs.prefect.io/core/task_library/azure.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/azure_ml.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Azure ML</p>](https://docs.prefect.io/core/task_library/azureml.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dbt.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>DBT</p>](https://docs.prefect.io/core/task_library/dbt.html) |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/docker.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Docker</p>](https://docs.prefect.io/core/task_library/docker.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dropbox.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Dropbox</p>](https://docs.prefect.io/core/task_library/dropbox.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/email.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Email</p>](https://docs.prefect.io/core/task_library/email.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/google_cloud.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Google Cloud</p>](https://docs.prefect.io/core/task_library/gcp.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/github.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>GitHub</p>](https://docs.prefect.io/core/task_library/github.html) |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/jira.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Jira</p>](https://docs.prefect.io/core/task_library/jira.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/kubernetes.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Kubernetes</p>](https://docs.prefect.io/core/task_library/kubernetes.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/postgres.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>PostgreSQL</p>](https://docs.prefect.io/core/task_library/postgres.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/python.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Python</p>](https://docs.prefect.io/core/task_library/function.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/pushbullet.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Pushbullet</p>](https://docs.prefect.io/core/task_library/pushbullet.html) |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/redis.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Redis</p>](https://docs.prefect.io/core/task_library/redis.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/rss.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>RSS</p>](https://docs.prefect.io/core/task_library/rss.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/shell.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Shell</p>](https://docs.prefect.io/core/task_library/shell.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/slack.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Slack</p>](https://docs.prefect.io/core/task_library/slack.html)| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/snowflake.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Snowflake</p>](https://docs.prefect.io/core/task_library/snowflake.html) |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/spacy.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>SpaCy</p>](https://docs.prefect.io/core/task_library/spacy.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/sqlite.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>SQLite</p>](https://docs.prefect.io/core/task_library/sqlite.html) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/twitter.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Twitter</p>](https://docs.prefect.io/core/task_library/twitter.html) |

### Deployment & Execution

|       |       |       |       |       |
| :---: | :---: | :---: | :---: | :---: |
| <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/azure.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Azure</p>](https://azure.microsoft.com/en-us/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/aws.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>AWS</p>](https://aws.amazon.com/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/dask.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Dask</p>](https://dask.org/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/docker.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Docker</p>](https://www.docker.com/) | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/google_cloud.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Google Cloud</p>](https://cloud.google.com/)
<img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/kubernetes.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Kubernetes</p>](https://kubernetes.io/) | | | | <img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/logos/shell.png" height=128 width=128 style="max-height: 128px; max-width: 128px;"> [<p>Universal Deploy</p>](https://medium.com/the-prefect-blog/introducing-prefect-universal-deploy-7992283e5911)

## Resources

Prefect provides a variety of resources to help guide you to a successful outcome.

We are committed to ensuring a positive environment, and all interactions are governed by our [Code of Conduct](https://docs.prefect.io/core/code_of_conduct.html).

### Documentation

Prefect's documentation -- including concepts, tutorials, and a full API reference -- is always available at [docs.prefect.io](https://docs.prefect.io).

Instructions for contributing to documentation can be found in the [development guide](https://docs.prefect.io/core/development/documentation.html).

### Slack Community

Join our [Slack](https://join.slack.com/t/prefect-community/shared_invite/enQtODQ3MTA2MjI4OTgyLTliYjEyYzljNTc2OThlMDE4YmViYzk3NDU4Y2EzMWZiODM0NmU3NjM0NjIyNWY0MGIxOGQzODMxNDMxYWYyOTE) to chat about Prefect, ask questions, and share tips.

### Blog

Visit the [Prefect Blog](https://medium.com/the-prefect-blog) for updates and insights from the Prefect team.

### Support

Prefect offers a variety of community and premium [support options](https://www.prefect.io/support) for users of both Prefect Core and Prefect Cloud.

### Contributing

Read about Prefect's [community](https://docs.prefect.io/core/community.html) or dive in to the [development guides](https://docs.prefect.io/core/development/overview.html) for information about contributions, documentation, code style, and testing.

## Installation

### Requirements

Prefect requires Python 3.6+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

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

Prefect is variously licensed under the [Apache Software License Version 2.0](https://www.apache.org/licenses/LICENSE-2.0) or the [Prefect Community License](https://www.prefect.io/legal/prefect-community-license).

All code except the `/server` directory is Apache 2.0-licensed unless otherwise noted. The `/server` directory is licensed under the Prefect Community License.
