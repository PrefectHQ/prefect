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

# Prefect 2

Prefect 2 is the second-generation dataflow coordination and orchestration platform from [Prefect](https://www.prefect.io).

Prefect 2 has been designed from the ground up to handle the dynamic, scalable workloads that the modern data stack demands. Powered by a brand-new, asynchronous rules engine, it represents an enormous amount of research, development, and dedication to a simple idea:

_**You should love your workflows again.**_

[Read the docs](https://docs.prefect.io/), run the code, or host the UI. Join thousands of community members in [our Slack community](https://www.prefect.io/slack) to share your thoughts and feedback. Thanks for being part of the mission to build a new kind of workflow system and, of course, **happy engineering!**

**"Don't Panic"**

Still using Prefect 1 Core and Server? Find the [legacy Prefect 1 docs](https://docs-v1.prefect.io/) at [https://docs-v1.prefect.io/](https://docs.prefect.io/).

---

## Coordinating the world's dataflows

Powered by a new, asynchronous engine, Prefect is the easiest way to transform any function into a unit of work that can be observed and governed by orchestration rules. 

Add workflow features like retries, distributed execution, scheduling, caching, and much more, with minimal changes to your code. Every activity is tracked and becomes visible in the Prefect server or Prefect Cloud dashboard.

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

After running some flows, fire up the Prefect UI to gain insight into their execution:

```bash
prefect server start
```

![](/docs/img/ui/prefect-dashboard.png)

From here, you can continue to use Prefect interactively or set up automated [deployments](https://docs.prefect.io/concepts/deployments).

## Next steps

Prefect 2 was designed to be incrementally adopted into your workflows, and our documentation is organized to support your exploration as much as possible. It is organized into four main sections whose applicability will depend on your objectives and comfort level.

### Getting started

Begin by [installing Prefect](https://docs.prefect.io/getting-started/installation) on your machine--Prefect currently supports the following Python versions: 3.7, 3.8, 3.9, 3.10. Then follow one of our [friendly tutorials](https://docs.prefect.io/tutorials/first-steps) to learn by example. See the [Getting Started overview](https://docs.prefect.io/getting-started/overview) for more.

### Concepts

Learn more about Prefect's features and design by reading our in-depth [concept docs](https://docs.prefect.io/concepts/overview). These are intended to introduce the building blocks of Prefect, build up to orchestration and deployment, and finally cover some of the advanced use cases that Prefect makes possible.

### Frequently asked questions

Prefect 2 represents a fundamentally new way of building and orchestrating data workflows. Learn more about the project by reading our [FAQ](https://docs.prefect.io/faq).

### API reference

Prefect provides a number of programmatic workflow interfaces, each of which is documented in the [API Reference](https://docs.prefect.io/api-ref/overview). This is where you can learn how a specific function works, or see the expected payload for a REST endpoint.

### Contributing

See our [documentation on contributing to Prefect 2](https://docs.prefect.io/contributing/overview/).


## Join the community

Prefect 2 was made possible by the fastest-growing community of data engineers. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more, ask questions, or get help with workflow design. The [Prefect Discourse](https://discourse.prefect.io/) is an additional community-driven knowledge base to find answers to your Prefect-related questions. Join us and thousands of friendly data engineers to help build a new kind of workflow system.
