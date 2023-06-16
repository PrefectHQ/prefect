---
description: Learn the basics of defining and running flows.
tags:
    - tutorial
    - getting started
    - basics
    - flows
    - logging
    - parameters
    - retries
---
## What is a flow?

A [flow](/concepts/flows/) is the basis of all Prefect workflows, it's a Python function decorated with a `@flow` decorator.

Some important points about flows:

1. All Prefect workflows are defined within the context of a flow.
2. Every Prefect workflow must contain at least one `flow` function that serves as the entrypoint for execution of the flow.
3. Flows can include calls to tasks as well as to child flows, which we call "subflows" in this context. At a high level, this is just like writing any other Python application: you organize specific, repetitive work into tasks, and call those tasks from flows.

The simplest way get started with Prefect is to import and annotate your Python function with the [@flow](/api-ref/prefect/flows/#prefect.flows.flow) decorator. The script below fetches statistics about the main Prefect repository. Let's turn it into a Prefect flow:

```python hl_lines="2 5"
import httpx
from prefect import flow


@flow
def get_repo_info():
    url = "https://api.github.com/repos/PrefectHQ/prefect"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info()
```

Running this flow in your terminal will result in some interesting output:

<div class="terminal">
```bash
12:47:42.792 | INFO    | prefect.engine - Created flow run 'ludicrous-warthog' for flow 'get-repo-info'
PrefectHQ/prefect repository statistics 🤓:
Stars 🌠 : 12146
Forks 🍴 : 1245
12:47:45.008 | INFO    | Flow run 'ludicrous-warthog' - Finished in state Completed()
```
</div>

## Parameters

As with any Python function, you can pass arguments. The positional and keyword arguments defined on your flow function are called parameters. Prefect will automatically perform type conversion by using any provided type hints. Let's make the repository a parameter:

```python hl_lines="6"
import httpx
from prefect import flow


@flow
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info()
```

## Logging

Prefect enables you to log a variety of useful information about your flow and task runs, capturing information about your workflows for purposes such as monitoring, troubleshooting, and auditing. Let's add some logging to our flow:

```python hl_lines="2 11-14"
import httpx
from prefect import flow, get_run_logger


@flow
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    logger = get_run_logger()
    logger.info(f"PrefectHQ/prefect repository statistics 🤓:")
    logger.info(f"Stars 🌠 : {repo['stargazers_count']}")
    logger.info(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info()
```

Now the output looks more consistent:

<div class="terminal">
```bash
12:47:42.792 | INFO    | prefect.engine - Created flow run 'ludicrous-warthog' for flow 'get-repo-info'
PrefectHQ/prefect repository statistics 🤓:
12:47:43.016 | INFO    | Flow run 'ludicrous-warthog' - Stars 🌠 : 12146
12:47:43.042 | INFO    | Flow run 'ludicrous-warthog' - Forks 🍴 : 1245
12:47:45.008 | INFO    | Flow run 'ludicrous-warthog' - Finished in state Completed()
```
</div>

Prefect can also capture `print` statements as info logs by specifying `log_prints=True` in your `flow` decorator (e.g. `@flow(log_prints=True)`).

## Retries

So far our script works, but in the future, the GitHub API may be temporarily unavailable or you may hit a rate limit. Let's add retries to make our script resilient:

```python hl_lines="7"
import httpx
from prefect import flow, get_run_logger


@flow
def get_repo_info(
    repo_name: str = "PrefectHQ/prefect", retries=3, retry_delay_seconds=5
):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    logger = get_run_logger()
    logger.info(f"PrefectHQ/prefect repository statistics 🤓:")
    logger.info(f"Stars 🌠 : {repo['stargazers_count']}")
    logger.info(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info()
```

## Next Steps

As you have seen, adding a flow decorator converts our Python function to a resilient and observable workflow. In the next section you'll supercharge our flow by using tasks to organize the workflow's complexity.
