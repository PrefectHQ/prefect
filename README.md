<p align="center"><img src="https://github.com/PrefectHQ/prefect/assets/3407835/c654cbc6-63e8-4ada-a92a-efd2f8f24b85" width=1000></p>

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/prefecthq/prefect/" alt="Stars">
        <img src="https://img.shields.io/github/stars/prefecthq/prefect?color=0052FF&labelColor=090422" /></a>
    <a href="https://pepy.tech/badge/prefect/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/prefecthq/prefect/pulse" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/prefecthq/prefect?color=0052FF&labelColor=090422" /></a>
    <br>
    <a href="https://prefect.io/slack" alt="Slack">
        <img src="https://img.shields.io/badge/slack-join_community-red.svg?color=0052FF&labelColor=090422&logo=slack" /></a>
    <a href="https://discourse.prefect.io/" alt="Discourse">
        <img src="https://img.shields.io/badge/discourse-browse_forum-red.svg?color=0052FF&labelColor=090422&logo=discourse" /></a>
    <a href="https://www.youtube.com/c/PrefectIO/" alt="YouTube">
        <img src="https://img.shields.io/badge/youtube-watch_videos-red.svg?color=0052FF&labelColor=090422&logo=youtube" /></a>
</p>

# Prefect

Prefect is an orchestration and observability platform for building, observing, and triaging workflows.
It's the simplest way to transform Python code into an interactive workflow application.

Prefect allows you to expose your workflows through an API so teams dependent on you can programmatically access your pipelines, business logic, and more.
Prefect also allows you to standardize workflow development and deployment across your organization.

With Prefect, you can build resilient, dynamic workflows that react to the world around them and recover from unexpected changes.
With just a few decorators, Prefect supercharges your code with features like automatic retries, distributed execution, scheduling, caching, and much more.

Every activity is tracked and can be monitored with a self-hosted [Prefect server](https://docs.prefect.io/latest/guides/host/) instance or managed [Prefect Cloud](https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss_gh_repo&utm_term=none&utm_content=none) dashboard.

## Getting started

Prefect requires Python 3.8 or later. To [install Prefect 2](https://docs-2.prefect.io/getting-started/installation/), run the following command:

```bash
pip install 'prefect<3'
```

See the [Prefect 3 docs](https://docs.prefect.io) to learn about the benefits of Prefect 3 and how to install it.

Then create and run a Python file that uses Prefect `flow` and `task` decorators to orchestrate and observe your workflow - in this case, a simple script that fetches the number of GitHub stars from a repository:

```python
from prefect import flow, task
from typing import List
import httpx


@task(log_prints=True)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")


@flow(name="GitHub Stars")
def github_stars(repos: List[str]):
    for repo in repos:
        get_stars(repo)


# run the flow!
if __name__=="__main__":
    github_stars(["PrefectHQ/Prefect"])
```

Fire up the Prefect UI to see what happened:

```bash
prefect server start
```

![Prefect UI dashboard](/docs/img/ui/cloud-dashboard.png)

To run your workflow on a schedule, turn it into a deployment and schedule it to run every minute by changing the last line of your script to the following:

```python
    github_stars.serve(name="first-deployment", cron="* * * * *")
```

You now have a server running locally that is looking for scheduled deployments!
Additionally you can run your workflow manually from the UI or CLI - and if you're using Prefect Cloud, you can even run deployments in response to [events](https://docs.prefect.io/latest/concepts/automations/).

## Prefect Cloud

Stop worrying about your workflows.
Prefect Cloud allows you to centrally deploy, monitor, and manage the data workflows you support. With managed orchestration, automations, and webhooks, all backed by enterprise-class security, build production-ready code quickly and reliably.

Read more about Prefect Cloud [here](https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss_gh_repo&utm_term=none&utm_content=none) or sign up to [try it for yourself](https://app.prefect.cloud?utm_source=oss&utm_medium=oss&utm_campaign=oss_gh_repo&utm_term=none&utm_content=none).

![Prefect Automations](/docs/img/ui/automations.png)

## prefect-client

If your use case is geared towards communicating with Prefect Cloud or a remote Prefect server, check out our
[prefect-client](https://pypi.org/project/prefect-client/). It was designed to be a lighter-weight option for accessing
client-side functionality in the Prefect SDK and is ideal for use in ephemeral execution environments.

## Next steps

There's lots more you can do to orchestrate and observe your workflows with Prefect!
Start with our [friendly tutorial](https://docs.prefect.io/tutorials) or explore the [core concepts of Prefect workflows](https://docs.prefect.io/concepts/).

## Join the community

Prefect is made possible by the fastest growing community of thousands of friendly data engineers. Join us in building a new kind of workflow system. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more about Prefect, ask questions, or get help with workflow design. All community forums, including code contributions, issue discussions, and slack messages are subject to our [Code of Conduct](https://discourse.prefect.io/faq).

## Contribute

See our [documentation on contributing to Prefect](https://docs.prefect.io/contributing/overview/).

Thanks for being part of the mission to build a new kind of workflow system and, of course, **happy engineering!**
