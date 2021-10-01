---
hide:
  - navigation
  - toc
---
<figure markdown=1>
![](./img/prefect-orion-logo-dark.svg){width=500px}
</figure>

#
**Don't Panic.** Prefect Orion is the second-generation workflow orchestration engine from [Prefect](https://www.prefect.io), now available as a technical preview. 

Orion was designed from the ground up to handle the dynamic, scalable workloads that the modern data stack demands. Powered by a brand-new, async rules engine, it represents years of research, development, and dedication to a simple idea: **you should love your workflows again**.

Read the docs, run the code, or host the UI. Join thousands of community members in [Slack](https://www.prefect.io/slack) to share your thoughts and feedback.

!!! info "Please note"
    Orion is under active development and will change rapidly. For production use, please prefer [Prefect Core](https://github.com/prefecthq/prefect).

---
## Hello, world!

Prefect is the easiest way to transform any function into an orchestratable task. Add workflow features like retries, distributed execution, scheduling, caching, and much more, with minimal changes to your data. Every activity is tracked and visible in the Orion UI.

=== "Basic orchestration" 

    Modify a script to automatically retry each task on failure.


    ```python hl_lines="1 6 13"
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
    github_stars(["PrefectHQ/Prefect", "PrefectHQ/Miter-Design"])
    ```

=== "Parallel execution"

    Scale tasks across a [Dask](https://dask.org) distributed cluster by changing the flow's `executor`.

    ```python hl_lines="2 14"
    from prefect import flow, task
    from prefect.executors import DaskExecutor
    from typing import List
    import httpx


    @task(retries=3)
    def get_stars(repo: str):
        url = f"https://api.github.com/repos/{repo}"
        count = httpx.get(url).json()["stargazers_count"]
        print(f"{repo} has {count} stars!")


    @flow(name="Github Stars", executor=DaskExecutor())
    def github_stars(repos: List[str]):
        for repo in repos:
            get_stars(repo)


    # run the flow!
    github_stars(["PrefectHQ/Prefect", "PrefectHQ/Miter-Design"])
    ```

=== "Async concurrency"

    With native async support, concurrent parallelism is easy. Asynchronous flows can include a mix of synchronous and asynchronous tasks, just like Python.

    ```python hl_lines="3 7-9 15-16 20"
    from prefect import flow, task
    from typing import List
    import httpx, asyncio


    @task(retries=3)
    async def get_stars(repo: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.github.com/repos/{repo}")
        count = response.json()["stargazers_count"]
        print(f"{repo} has {count} stars!")


    @flow(name="Github Stars")
    async def github_stars(repos: List[str]):
        await asyncio.gather(*[get_stars(repo) for repo in repos])


    # run the flow!
    await asyncio.run(github_stars(["PrefectHQ/Prefect", "PrefectHQ/Miter-Design"]))
    ```


After running any of these flows, fire up the UI to gain insight into their execution. You can continue to use Prefect interactively or set up automated [deployments](concepts/deployments.md).

---

## [Getting Started](getting-started/overview/)
[Install](getting-started/installation.md) Prefect, then dive into the [tutorial](tutorials/first-steps/).

## [Concepts](concepts/overview.md)

Learn more about Orion's design by reading our [concept docs](concepts/overview.md).

## [Frequently Asked Questions](faq.md)

Orion represents a fundamentally new way of building and orchestrating data workflows. Learn more about our plans by reading the [FAQ](faq.md).
