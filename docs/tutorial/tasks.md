---
description: Learn the basics of adding tasks to our flow.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - caching
    - concurrency
    - subflows
---

In this page of the tutorial, you create a flow with tasks, subflows, retries, logging, caching, and concurrent execution.

## Key points

* Tasks represent individual units of work within a flow that you can execute concurrently.
* You can only call tasks from within a flow. Tasks can't call other tasks directly.
* Not all flow functions need to be tasks. Use them only when their features provide a benefit.

## Build tasks

You can build a task by using the `@task` decorator and calling it within a flow:

```python hl_lines="2 5-9 15" title="repo_info.py"
import httpx
from prefect import flow, task
from typing import Optional

@task
def get_url(url: str, params: Optional[dict[str, any]] = None):
    response = httpx.get(url, params=params)
    response.raise_for_status()
    return response.json()


@flow(retries=3, retry_delay_seconds=5, log_prints=True)
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    url = f"https://api.github.com/repos/{repo_name}"
    repo_stats = get_url(url)
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo_stats['stargazers_count']}")
    print(f"Forks 🍴 : {repo_stats['forks_count']}")

if __name__ == "__main__":
    get_repo_info()
```

Running the flow in your terminal results in the following:

<div class="terminal">
```bash
09:55:55.412 | INFO    | prefect.engine - Created flow run 'great-ammonite' for flow 'get-repo-info'
09:55:55.499 | INFO    | Flow run 'great-ammonite' - Created task run 'get_url-0' for task 'get_url'
09:55:55.500 | INFO    | Flow run 'great-ammonite' - Executing 'get_url-0' immediately...
09:55:55.825 | INFO    | Task run 'get_url-0' - Finished in state Completed()
09:55:55.827 | INFO    | Flow run 'great-ammonite' - PrefectHQ/prefect repository statistics 🤓:
09:55:55.827 | INFO    | Flow run 'great-ammonite' - Stars 🌠 : 12157
09:55:55.827 | INFO    | Flow run 'great-ammonite' - Forks 🍴 : 1251
09:55:55.849 | INFO    | Flow run 'great-ammonite' - Finished in state Completed('All states completed.')
```
</div>

You should also be able to see this task and its dependencies in the flow run graph in the UI.

## Reuse tasking results

Using tasks, you can efficiently reuse task results that are expensive to reproduce with every flow run or if the inputs to a task remain unchanged.

To enable caching:

* Import the Prefect [`task_input_hash`](/api-ref/prefect/tasks/#prefect.tasks.task_input_hash) library.
* Specify a `cache_key_fn` function that returns a cache key — on your task. 
* Optionally provide a `cache_expiration timedelta` indicating when the cache expires.

Let's add caching to our `get_url` task:

```python hl_lines="2 4 7"
import httpx
from datetime import timedelta
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from typing import Optional


@task(cache_key_fn=task_input_hash, 
      cache_expiration=timedelta(hours=1),
      )
def get_url(url: str, params: Optional[dict[str, any]] = None):
    response = httpx.get(url, params=params)
    response.raise_for_status()
    return response.json()
```

You can test this caching behavior by using a personal repository as your workflow parameter - give it a star, or remove a star - and see how the output of this task changes (or doesn't) by running your flow multiple times.

!!! warning "Task results and caching"
    Task results are cached in memory during a flow run and persisted to your home directory by default.
    Prefect Cloud only stores the cache key, not the data itself.

## Execute multiple tasks asynchronously

Let's expand our script to calculate the average open issues per user. This requires making more requests:

```python hl_lines="14-24 30-31 35" title="repo_info.py"
import httpx
from datetime import timedelta
from prefect import flow, task
from prefect.tasks import task_input_hash
from typing import Optional


@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def get_url(url: str, params: Optional[dict[str, any]] = None):
    response = httpx.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_open_issues(repo_name: str, open_issues_count: int, per_page: int = 100):
    issues = []
    pages = range(1, -(open_issues_count // -per_page) + 1)
    for page in pages:
        issues.append(
            get_url(
                f"https://api.github.com/repos/{repo_name}/issues",
                params={"page": page, "per_page": per_page, "state": "open"},
            )
        )
    return [i for p in issues for i in p]


@flow(retries=3, retry_delay_seconds=5, log_prints=True)
def get_repo_info(repo_name: str = "PrefectHQ/prefect"):
    repo_stats = get_url(f"https://api.github.com/repos/{repo_name}")
    issues = get_open_issues(repo_name, repo_stats["open_issues_count"])
    issues_per_user = len(issues) / len(set([i["user"]["id"] for i in issues]))
    print(f"{repo_name} repository statistics 🤓:")
    print(f"Stars 🌠 : {repo_stats['stargazers_count']}")
    print(f"Forks 🍴 : {repo_stats['forks_count']}")
    print(f"Average open issues per user 💌 : {issues_per_user:.2f}")


if __name__ == "__main__":
    get_repo_info()

```

Now we're fetching the data we need, but the requests are happening sequentially.
Tasks expose a [`submit`](/api-ref/prefect/tasks/#prefect.tasks.Task.submit) method that changes the execution from sequential to concurrent.
In our specific example, we also need to use the [`result`](/api-ref/prefect/futures/#prefect.futures.PrefectFuture.result) method because we are unpacking a list of return values:

```python hl_lines="6 11"
def get_open_issues(repo_name: str, open_issues_count: int, per_page: int = 100):
    issues = []
    pages = range(1, -(open_issues_count // -per_page) + 1)
    for page in pages:
        issues.append(
            get_url.submit(
                f"https://api.github.com/repos/{repo_name}/issues",
                params={"page": page, "per_page": per_page, "state": "open"},
            )
        )
    return [i for p in issues for i in p.result()]
```

The logs show that each task is running concurrently:

<div class="terminal">

```bash
12:45:28.241 | INFO    | prefect.engine - Created flow run 'intrepid-coua' for flow 'get-repo-info'
12:45:28.311 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-0' for task 'get_url'
12:45:28.312 | INFO    | Flow run 'intrepid-coua' - Executing 'get_url-0' immediately...
12:45:28.543 | INFO    | Task run 'get_url-0' - Finished in state Completed()
12:45:28.583 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-1' for task 'get_url'
12:45:28.584 | INFO    | Flow run 'intrepid-coua' - Submitted task run 'get_url-1' for execution.
12:45:28.594 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-2' for task 'get_url'
12:45:28.594 | INFO    | Flow run 'intrepid-coua' - Submitted task run 'get_url-2' for execution.
12:45:28.609 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-4' for task 'get_url'
12:45:28.610 | INFO    | Flow run 'intrepid-coua' - Submitted task run 'get_url-4' for execution.
12:45:28.624 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-5' for task 'get_url'
12:45:28.625 | INFO    | Flow run 'intrepid-coua' - Submitted task run 'get_url-5' for execution.
12:45:28.640 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-6' for task 'get_url'
12:45:28.641 | INFO    | Flow run 'intrepid-coua' - Submitted task run 'get_url-6' for execution.
12:45:28.708 | INFO    | Flow run 'intrepid-coua' - Created task run 'get_url-3' for task 'get_url'
12:45:28.708 | INFO    | Flow run 'intrepid-coua' - Submitted task run 'get_url-3' for execution.
12:45:29.096 | INFO    | Task run 'get_url-6' - Finished in state Completed()
12:45:29.565 | INFO    | Task run 'get_url-2' - Finished in state Completed()
12:45:29.721 | INFO    | Task run 'get_url-5' - Finished in state Completed()
12:45:29.749 | INFO    | Task run 'get_url-4' - Finished in state Completed()
12:45:29.801 | INFO    | Task run 'get_url-3' - Finished in state Completed()
12:45:29.817 | INFO    | Task run 'get_url-1' - Finished in state Completed()
12:45:29.820 | INFO    | Flow run 'intrepid-coua' - PrefectHQ/prefect repository statistics 🤓:
12:45:29.820 | INFO    | Flow run 'intrepid-coua' - Stars 🌠 : 12159
12:45:29.821 | INFO    | Flow run 'intrepid-coua' - Forks 🍴 : 1251
Average open issues per user 💌 : 2.27
12:45:29.838 | INFO    | Flow run 'intrepid-coua' - Finished in state Completed('All states completed.')
```

</div>

## Organize multiple tasks

Subflows are a great way to organize multiple tasks and offer more visibility within the UI.

Let's add a `flow` decorator to our `get_open_issues` function:

```python hl_lines="1"
@flow
def get_open_issues(repo_name: str, open_issues_count: int, per_page: int = 100):
    issues = []
    pages = range(1, -(open_issues_count // -per_page) + 1)
    for page in pages:
        issues.append(
            get_url.submit(
                f"https://api.github.com/repos/{repo_name}/issues",
                params={"page": page, "per_page": per_page, "state": "open"},
            )
        )
    return [i for p in issues for i in p.result()]
```

Parent flow runs trigger subflow runs that are trackable and inspectable indepedently in the UI.

## Next steps

We now have a flow with tasks, subflows, retries, logging, caching, and concurrent execution. In the next section, run your flow on a schedule or external infrastructure by [deploying your flow](/tutorial/deployments/).
