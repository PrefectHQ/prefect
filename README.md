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

Prefect is an orchestration and observation platform for building and reacting to workflows.
It's the simplest way to transform Python code into an interactive workflow application.

With Prefect you can standardize workflow deployment across your organization.

You can build resilient, dynamic workflows that react to the world around them and recover from unexpected changes.

With just a few decorators, Prefect supercharges your code with features like automatic retries, distributed execution, scheduling, caching, and much more.

Workflow activity is tracked and can be monitored with a self-hosted [Prefect server](https://docs.prefect.io/latest/guides/host/) instance or managed [Prefect Cloud](https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss_gh_repo&utm_term=none&utm_content=none) dashboard.

## Getting started

Prefect requires Python 3.9 or later. To [install the latest or upgrade to the latest version of Prefect](https://docs.prefect.io/getting-started/installation/), run the following command:

```bash
pip install -U prefect
```

Then create and run a Python file that uses Prefect `flow` and `task` decorators to orchestrate and observe your workflow - in this case, a simple script that fetches the number of GitHub stars from a repository:

```python
from prefect import flow, task
from typing import list
import httpx


@task(log_prints=True)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")


@flow(name="GitHub Stars")
def github_stars(repos: list[str]):
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

![Prefect UI dashboard](https://github.com/PrefectHQ/prefect/blob/main/docs/images/cloud-overview1.png?raw=true)

To run your workflow on a schedule, turn it into a deployment and schedule it to run every minute by changing the last line of your script to the following:

```python
if __name__ == "__main__":
    github_stars.serve(name="first-deployment", cron="* * * * *")
```

You now have a server running locally that is looking for scheduled deployments!
Additionally you can run your workflow manually from the UI or CLI - and if you're using Prefect Cloud, you can even run deployments in response to [events](https://docs.prefect.io/latest/concepts/automations/).

## Prefect Cloud

Stop worrying about your workflows.
Prefect Cloud allows you to centrally deploy, monitor, and manage the data workflows you support. With managed orchestration, automations, and webhooks, all backed by enterprise-class security, build production-ready code quickly and reliably.

Read more about Prefect Cloud [here](https://www.prefect.io/cloud-vs-oss?utm_source=oss&utm_medium=oss&utm_campaign=oss_gh_repo&utm_term=none&utm_content=none) or sign up to [try it for yourself](https://app.prefect.cloud?utm_source=oss&utm_medium=oss&utm_campaign=oss_gh_repo&utm_term=none&utm_content=none).

![Prefect Automations](https://github.com/PrefectHQ/prefect/blob/main/docs/images/automations-1.png?raw=true)
![Prefect Automations](https://github.com/PrefectHQ/prefect/blob/main/docs/images/automations-2.png?raw=true)
![Prefect Automations](https://github.com/PrefectHQ/prefect/blob/main/docs/images/automations-4.png?raw=true)


## prefect-client

If your use case is geared towards communicating with Prefect Cloud or a remote Prefect server, check out our
[prefect-client](https://pypi.org/project/prefect-client/). It is a lighter-weight option for accessing client-side functionality in the Prefect SDK and is ideal for use in ephemeral execution environments.

## Next steps

- Check out the [Docs](https://docs.prefect.io/).
- Join the {Prefect Slack community](https://prefect.io/slack).
- Learn how to [contribute to Prefect](https://docs.prefect.io/contributing/overview/).
