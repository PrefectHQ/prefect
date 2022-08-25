---
sidebarDepth: 0
editLink: false
---


<div align="center" style="margin-bottom:40px;">
<img src="/assets/prefect-logo-gradient-navy.svg"  width=500 >
</div>

# API Reference

This API reference is automatically generated from Prefect's source code
and unit-tested to ensure it's up to date.


## Hello, world! 👋

We've rebuilt data engineering for the data science era.

Prefect is a new workflow management system, designed for modern infrastructure and powered by the open-source Prefect Core workflow engine. Users organize `Tasks` into `Flows`, and Prefect takes care of the rest.

Read the [docs](/core/); get the [code](#installation); ask us [anything](https://www.prefect.io/slack); chat with the community via [Prefect Discourse](https://discourse.prefect.io/)!

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

For more detail, please see the [Core docs](/core/)

### UI and Server

<p align="center" style="margin-bottom:40px;">
<img src="https://raw.githubusercontent.com/PrefectHQ/prefect/master/docs/.vuepress/public/orchestration/ui/dashboard-overview2.png"  height=440 style="max-height: 440px;">
</p>

In addition to the [Prefect Cloud](https://www.prefect.io/cloud) platform, Prefect includes an open-source backend for orchestrating and managing flows, consisting primarily of [Prefect Server](https://github.com/prefecthq/server) and [Prefect UI](https://github.com/prefecthq/ui). This local server stores flow metadata in a Postgres database and exposes a GraphQL API.

Before running the server for the first time, run `prefect backend server` to configure Prefect for local orchestration. Please note the server requires [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/) to be running.

To start the server, UI, and all required infrastructure, run:

```
prefect server start
```

Once all components are running, you can view the UI by visiting [http://localhost:8080](http://localhost:8080).

Please note that executing flows from the server requires at least one Prefect Agent to be running: `prefect agent local start`.

Finally, to register any flow with the server, call `flow.register()`. For more detail, please see the [orchestration docs](/orchestration/).

## "...Prefect?"

From the Latin _praefectus_, meaning "one who is in charge", a prefect is an official who oversees a domain and makes sure that the rules are followed. Similarly, Prefect is responsible for making sure that workflows execute properly.

It also happens to be the name of a roving researcher for that wholly remarkable book, _The Hitchhiker's Guide to the Galaxy_.

## Integrations

Thanks to Prefect's growing task library and deep ecosystem integrations, building data applications is easier than ever.

Something missing? Open a [feature request](https://github.com/PrefectHQ/prefect/issues/new/choose) or [contribute a PR](/core/development/overview.html)! Prefect was designed to make adding new functionality extremely easy, whether you build on top of the open-source package or maintain an internal task library for your team.

### Task Library

The Prefect [Task Library](/core/task_library/overview.html) is a constantly growing list of pre-defined tasks that provide off-the-shelf functionality for working with a wide range of tools anywhere from shell script execution to Kubernetes job management to sending tweets.

## Resources

Prefect provides a variety of resources to help guide you to a successful outcome.

We are committed to ensuring a positive environment, and all interactions are governed by our [Code of Conduct](/core/code_of_conduct.html).

### Documentation

Prefect's documentation -- including concepts, tutorials, and a full API reference -- is always available at [docs-v1.prefect.io](https://docs-v1.prefect.io).

Instructions for contributing to documentation can be found in the [development guide](/core/development/documentation.html).

### Prefect Discourse

Join our [forum](https://discourse.prefect.io/) to share knowledge, discuss ideas, find answers to common questions and get support.

### Slack Community

Join our [Slack](https://www.prefect.io/slack) to chat about Prefect, ask questions, and share tips.

### Blog

Visit the [Prefect Blog](https://medium.com/the-prefect-blog) for updates and insights from the Prefect team.

### Support

Prefect offers a variety of community and premium [support options](https://www.prefect.io/support) for users of both Prefect Core and Prefect Cloud.

### Contributing

Read about Prefect's [community](/core/community.html) or dive in to the [development guides](/core/development/overview.html) for information about contributions, documentation, code style, and testing.

## Installation

### Requirements

Prefect requires Python 3.6+. If you're new to Python, we recommend installing the [Anaconda distribution](https://www.anaconda.com/distribution/).

### Latest Release

**Note:** with the general availability of [Prefect 2.0](https://docs.prefect.io/getting-started/installation/), you will need to specify the Prefect version when installing or updating Prefect 1.0 via a package manager.

To install Prefect, run:

```bash
pip install "prefect==1.*"
```

If you prefer to use `conda`:

```bash
conda install -c conda-forge "prefect>=1.24,<2"
```

If you use `pipenv`:

```bash
pip install "prefect==1.*"
```

### Bleeding Edge

For development or just to try out the latest features, you may want to install Prefect directly from source.

Please note that the master branch of Prefect 1.0 is not guaranteed to be compatible with Prefect Cloud or the local server.

```bash
git clone https://github.com/PrefectHQ/prefect.git
pip install ./prefect
```

## License

Prefect Core is licensed under the [Apache Software License Version 2.0](https://www.apache.org/licenses/LICENSE-2.0). Please note that Prefect Core includes utilities for running [Prefect Server](https://www.github.com/prefecthq/server) and the [Prefect UI](https://www.github.com/prefecthq/ui), which are themselves licensed under the [Prefect Community License](https://www.prefect.io/legal/prefect-community-license).
<p class="auto-gen">This documentation was auto-generated from commit <a href='https://github.com/PrefectHQ/prefect/commit/n/a'>n/a</a> </br>on July 1, 2021 at 18:35 UTC</p>