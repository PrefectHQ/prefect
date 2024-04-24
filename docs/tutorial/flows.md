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
# Master workflow automations: Build flows

This page in the [tutorial](/tutorial) shows how to build flows.

Flows are the core building blocks for defining and managing workflows as code within Prefect. They serve as containers for your workflow logic.

## Before you begin

Complete the [Before you begin section](/tutorial/).

## Create a flow

The following function uses the [`httpx`](https://www.python-httpx.org/) Prefect dependency (an HTTP client library) and the `@flow` decorator to create a flow that fetches statistics about the [GitHub Prefect repository](https://github.com/PrefectHQ/prefect):

```python title="repo_info.py" hl_lines="2 5"
import httpx
from prefect import flow


@flow
def get_repo_info():
    url = "https://api.github.com/repos/PrefectHQ/prefect"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print("PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")

if __name__ == "__main__":
    get_repo_info()
```

Running this file results in the following output:

<div class="terminal">

```bash
12:47:42.792 | INFO | prefect.engine - Created flow run 'ludicrous-warthog' for
        flow 'get-repo-info'
PrefectHQ/prefect repository statistics 🤓:
Stars 🌠 : 12146
Forks 🍴 : 1245
12:47:45.008 | INFO | Flow run 'ludicrous-warthog' - Finished in state
        Completed()
```
</div>

## Parameters

You can pass positional and keyword arguments to a flow using parameters. Prefect automatically performs type conversion using any provided type hints.

Let's make the repository a string parameter with a default value:

```python hl_lines="6 7 11" title="repo_info.py"
import httpx
from prefect import flow

@flow
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info(repo_name="PrefectHQ/marvin")
```

We can call our flow with varying values for the `repo_name` parameter (including "bad" values):

<div class="terminal">

```bash
python repo_info.py
```

</div>

Try passing `repo_name="missing-org/missing-repo"`.

You should see:

<div class="terminal">

```bash
HTTPStatusError: Client error '404 Not Found' for url
        '<https://api.github.com/repos/missing-org/missing-repo>'

```

</div>

Now navigate to your [Prefect dashboard](link) and compare the displays for these two runs.

## Logging

Prefect enables you to log a variety of useful information about your flow runs, capturing information about your workflows for purposes such as monitoring, troubleshooting, and auditing.

Add logging to your flow to track progress and debug errors:

```python hl_lines="2 11-14" title="repo_info.py"
import httpx
from prefect import flow, get_run_logger


@flow
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    logger = get_run_logger()
    logger.info("%s repository statistics 🤓:", repo_name)
    logger.info(f"Stars 🌠 : %d", repo["stargazers_count"])
    logger.info(f"Forks 🍴 : %d", repo["forks_count"])
```

Your output should look more consistent:

<div class="terminal">
```bash
12:47:42.792 | INFO    | prefect.engine - Created flow run 'ludicrous-warthog' for flow 'get-repo-info'
12:47:43.016 | INFO    | Flow run 'ludicrous-warthog' - PrefectHQ/prefect repository statistics 🤓:
12:47:43.016 | INFO    | Flow run 'ludicrous-warthog' - Stars 🌠 : 12146
12:47:43.042 | INFO    | Flow run 'ludicrous-warthog' - Forks 🍴 : 1245
12:47:45.008 | INFO    | Flow run 'ludicrous-warthog' - Finished in state Completed()
```
</div>

## Handle unexpected errors

If unexpected errors occur, such as the GitHub API is temporarily unavailable or rate limited, you can use [retries](/concepts/flows/#flow-settings) to help make your flow more resilient.

Let's add retry functionality to our example:

```python hl_lines="5" title="repo_info.py"
import httpx
from prefect import flow


@flow(retries=3, retry_delay_seconds=5, log_prints=True)
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    response = httpx.get(url)
    response.raise_for_status()
    repo = response.json()
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo['stargazers_count']}")
    print(f"Forks 🍴 : {repo['forks_count']}")

if __name__ == "__main__":
    get_repo_info()
```

## Next steps

Now that you've created a simple flow that uses logging and handles retries, you're ready to 
use [tasks](/tutorial/tasks/).
