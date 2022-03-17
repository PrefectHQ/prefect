<p align="center"><img src="https://images.ctfassets.net/gm98wzqotmnx/6rIpC9ZCAewsRGLwOw5BRe/bb17e1ef62f60d1ec32c1ae69487704c/prefect-2-logo-dark.png" width=1000></p>

# Prefect 2.0

A development repo for Prefect 2.0 and Orion. Documentation can be found at https://orion-docs.prefect.io/.

## Welcome!

Prefect 2.0 is powered by Orion, the second-generation workflow orchestration engine from [Prefect](https://www.prefect.io).

Prefect 2.0 has been designed from the ground up to handle the dynamic, scalable workloads that the modern data stack demands. Powered by Orion, a brand-new, asynchronous rules engine, it represents an enormous amount of research, development, and dedication to a simple idea:

_**You should love your workflows again.**_

Read the docs, run the code, or host the UI. Join thousands of community members in [our Slack community](https://www.prefect.io/slack) to share your thoughts and feedback. Thanks for being part of the mission to build a new kind of workflow system and, of course, **happy engineering!**

**"Don't Panic"**

Prefect 2.0 and Orion are under active development and may change rapidly. For production use, we recommend [Prefect Core](https://github.com/prefecthq/prefect).

---

## Hello, Orion!

Prefect is the easiest way to transform any function into a unit of work that can be observed and governed by orchestration rules.

Add workflow features like retries, distributed execution, scheduling, caching, and much more, with minimal changes to your code. Every activity is tracked and becomes visible in the Orion Dashboard.

Decorate functions to automatically retry them on failure while providing complete visibility in the Orion Dashboard.

```python
from prefect import flow, task
from typing import List
import httpx


@task(retries=3)
def get_stars(repo: str):
    url = f"https://api.github.com/repos/{repo}"
    count = httpx.get(url).json()["stargazers_count"]
    print(f"{repo} has {count} stars!")


@flow(name="Github Stars")
def github_stars(repos: List[str]):
    for repo in repos:
        get_stars(repo)


# run the flow!
github_stars(["PrefectHQ/Prefect", "PrefectHQ/miter-design"])
```

After running any running some flows, fire up the UI to gain insight into their execution:

```bash
prefect orion start
```

![](/docs/img/ui/orion-dashboard.png)

From here, you can continue to use Prefect interactively or set up automated [deployments](https://orion-docs.prefect.io/concepts/deployments).

## Next steps

Prefect 2.0 was designed to be incrementally adopted into your workflows, and our documentation is organized to support your exploration as much as possible. It is organized into four main sections whose applicability will depend on your objectives and comfort level.

### Getting started

Begin by [installing Prefect](https://orion-docs.prefect.io/getting-started/installation) on your machine, then follow one of our [friendly tutorials](https://orion-docs.prefect.io/tutorials/first-steps) to learn by example. See the [Getting Started overview](https://orion-docs.prefect.io/getting-started/overview) for more.


### Concepts

Learn more about Prefect's features and design by reading our in-depth [concept docs](https://orion-docs.prefect.io/concepts/overview). These are intended to introduce the building blocks of Prefect Orion, build up to orchestration and deployment, and finally cover some of the advanced use cases that Orion makes possible.

### Frequently asked questions

Prefect 2.0 represents a fundamentally new way of building and orchestrating data workflows. Learn more about the project by reading our [FAQ](https://orion-docs.prefect.io/faq).

### API reference

Prefect Orion provides a number of programmatic workflow interfaces, each of which is documented in the [API Reference](https://orion-docs.prefect.io/api-ref/overview). This is where you can learn how a specific function works, or see the expected payload for a REST endpoint.

### Contributing

See our [documentation on contributing to Prefect 2.0](https://orion-docs.prefect.io/contributing/overview/).


## Join the community

Prefect 2.0 was made possible by the fastest-growing community of data engineers. The [Prefect Slack community](https://prefect.io/slack) is a fantastic place to learn more, ask questions, or get help with workflow design. The [Prefect Discourse](https://discourse.prefect.io/) is an additional community-driven knowledge base to find answers to your Prefect-related questions. Join us and thousands of friendly data engineers to help build a new kind of workflow system.
