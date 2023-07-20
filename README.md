<p align="center"><img src="https://images.ctfassets.net/gm98wzqotmnx/6rIpC9ZCAewsRGLwOw5BRe/bb17e1ef62f60d1ec32c1ae69487704c/prefect-2-logo-dark.png" width=1000></p>

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
    <a href="https://prefect-community.slack.com" alt="Slack">
        <img src="https://img.shields.io/badge/slack-join_community-red.svg?color=0052FF&labelColor=090422&logo=slack" /></a>
    <a href="https://discourse.prefect.io/" alt="Discourse">
        <img src="https://img.shields.io/badge/discourse-browse_forum-red.svg?color=0052FF&labelColor=090422&logo=discourse" /></a>
    <a href="https://www.youtube.com/c/PrefectIO/" alt="YouTube">
        <img src="https://img.shields.io/badge/youtube-watch_videos-red.svg?color=0052FF&labelColor=090422&logo=youtube" /></a>
</p>

# Prefect

Prefect is an orchestrator for data-intensive workflows. It's the simplest way to transform any Python function into a unit of work that can be observed and orchestrated. With Prefect, you can build resilient, dynamic workflows that react to the world around them and recover from unexpected changes. With just a few decorators, Prefect supercharges your code with features like automatic retries, distributed execution, scheduling, caching, and much more. Every activity is tracked and can be monitored with the Prefect server or Prefect Cloud dashboard.

```python
from prefect import flow, task
from typing import List
import httpx


@task(retries=3)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")


@flow(name="GitHub Stars")
def github_stars(repos: List[str]):
    for repo in repos:
        get_stars(repo)


# run the flow!
github_stars(["PrefectHQ/Prefect"])
```

After running some flows, fire up the Prefect UI to see what happened:

```bash
prefect server start
```

![](/docs/img/ui/dashboard-oss.png)

From here, you can continue to use Prefect interactively or [deploy your flows](https://docs.prefect.io/concepts/deployments) to remote environments, running on a scheduled or event-driven basis.

## Getting Started

Prefect requires Python 3.8 or later. To [install Prefect](https://docs.prefect.io/getting-started/installation/), run the following command in a shell or terminal session:

```bash
pip install prefect
```

Start by then exploring the [core concepts of Prefect workflows](https://docs.prefect.io/concepts/), then follow one of our [friendly tutorials](https://docs.prefect.io/tutorials/first-steps) to learn by example.

## Join the community

Prefect is made possible by the fastest growing community of thousands of friendly data engineers. Join us in building a new kind of workflow system. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more about Prefect, ask questions, or get help with workflow design. The [Prefect Discourse](https://discourse.prefect.io/) is a community-driven knowledge base to find answers to your Prefect-related questions. All community forums, including code contributions, issue discussions, and slack messages are subject to our [Code of Conduct](https://discourse.prefect.io/faq).

## Contribute

See our [documentation on contributing to Prefect](https://docs.prefect.io/contributing/overview/).

Thanks for being part of the mission to build a new kind of workflow system and, of course, **happy engineering!**
