---
description: Learn the basics of adding tasks to our flow.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
---

## What is a task?

A [task](/concepts/tasks/) is a Python function decorated with a `@task` decorator. Tasks represent distinct pieces of work executed within a flow. While flows provide a high-level structure for executing your code, tasks help organize your code by adding an atomic component that can be orchestrated and observed within the context of a flow.

Flows and tasks share some common features:
* Both have metadata attributes such as name, description, and tags.
* Both support type-checked parameters, allowing you to define the expected data types of inputs and outputs.
* Both provide functionality for retries, timeouts, and other hooks to handle failure and completion events.

Network calls (such as our GET requests to the GitHub API) are particularly useful as tasks because they take advantage of task features such as retries, caching, and concurrency.

!!! warning "Tasks must be called from flows"
    All tasks must be called from within a flow. Tasks may not call other tasks directly.

!!! note "When to use tasks"
    Not all functions need be tasks. Use tasks when the features of tasks are useful.

Let's take our flow from before and move the request into a task:

```python hl_lines="2 5-10 17"
import httpx
from prefect import flow, task, get_run_logger


@task
def get_url(path: str):
    url = f"https://api.github.com/repos/{path}"
    response = httpx.get(url)
    response.raise_for_status()
    return response.json()


@flow
def get_repo_info(
    repo_name: str = "PrefectHQ/prefect", retries=3, retry_delay_seconds=5
):
    repo = get_url(repo_name)
    logger = get_run_logger()
    logger.info(f"PrefectHQ/prefect repository statistics 🤓:")
    logger.info(f"Stars 🌠 : {repo['stargazers_count']}")
    logger.info(f"Forks 🍴 : {repo['forks_count']}")


if __name__ == "__main__":
    get_repo_info()
```

Running the flow in your terminal will result in something like this:

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

If we click the link in our terminal and follow it to Prefect Cloud, we'll see something like this:

![Tasks provide greater visibility as well as concurrency](/img/tutorial/cloud-flow-run.png)

## Concurrency

Tasks also enable concurrency, allowing you to execute multiple tasks asynchronously. This concurrency can greatly enhance the efficiency and performance of your workflows.

## Caching

By encapsulating a specific unit of work within a `task`, you can define its inputs, outputs, and behavior. This modular approach allows for easier management and composition of complex workflows.

Some examples of task features include:

- Concurrency
- Caching
- Parallelism
- Concurrency Limits
- Tagging
- Retries
- Advanced dependency management

!!! warning Task Usage

    By separating network calls between tasks, Prefect features like caching or retries are most useful.

!!! note Complex workflows

    What if I have more complex workflows and want more information? 
    Subflows are a great way to organize your workflows and offer more visibility within the UI. 

### Subflow

Not only can you call task functions within a flow, but you can also call other flow functions! Child flows are called [subflows](https://docs.prefect.io/concepts/flows/#composing-flows) and allow you to efficiently manage, track, and version common multi-task logic.

We can replace the `@task` decorator with a `@flow` decorator on `calculate_average_commits`, which allows for more visibility on this flow pattern. 
```python
import httpx
from prefect import flow

@flow(log_prints = True)
def get_repo_info():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    if api_response.status_code == 200:
        repo_info = api_response.json()
        stars = repo_info['stargazers_count']
        forks = repo_info['forks_count']
        contributors_url = repo_info['contributors_url']
        contributors = get_contributors(contributors_url)
        average_commits = calculate_average_commits(contributors)
        print(f"PrefectHQ/prefect repository statistics 🤓:")
        print(f"Stars 🌠 : {stars}")
        print(f"Forks 🍴 : {forks}")
        print(f"Average commits per contributor 💌 : {average_commits:.2f}")
    else:
        raise Exception('Failed to fetch repository information.')
@task()
def get_contributors(url):
    response = httpx.get(url)
    if response.status_code == 200:
        contributors = response.json()
        return len(contributors)
    else:
        raise Exception('Failed to fetch contributors.')
@flow()
def calculate_average_commits(contributors):
    commits_url = f'https://api.github.com/repos/PrefectHQ/prefect/stats/contributors'
    response = httpx.get(commits_url)
    if response.status_code == 200:
        commit_data = response.json()
        total_commits = sum(c['total'] for c in commit_data)
        average_commits = total_commits / contributors
        return average_commits
    else:
        raise Exception('Failed to fetch commit information.')

if __name__ == '__main__':
    get_repo_info()
```

Whenever we run the parent flow is run, a new run will be generated for related functions within that as well. Not only is this run tracked as a subflow run of the main flow, but you can also inspect it independently in the UI!

You will be able to visualize this subflow pattern within your logging in the CLI. Note that a new subflow is generated for `calculate-average-commits`
<div class="terminal">
```bash
23:39:05.722 | INFO    | prefect.engine - Created flow run 'sparkling-mandrill' for flow 'get-repo-info'
23:39:05.723 | INFO    | Flow run 'sparkling-mandrill' - View at https://app.prefect.cloud/account/0ff44498-d380-4d7b-bd68-9b52da03823f/workspace/80d66ded-76f2-46fe-98e6-576ebe2a707c/flow-runs/flow-run/44a06d2d-a876-477b-98af-345baf05eba1
23:39:06.910 | INFO    | Flow run 'sparkling-mandrill' - Created subflow run 'dexterous-walrus' for flow 'calculate-average-commits'
23:39:06.912 | INFO    | Flow run 'dexterous-walrus' - View at https://app.prefect.cloud/account/0ff44498-d380-4d7b-bd68-9b52da03823f/workspace/80d66ded-76f2-46fe-98e6-576ebe2a707c/flow-runs/flow-run/02e8ecff-7e30-422b-a118-6f745fe1bc53
23:39:08.807 | INFO    | Flow run 'dexterous-walrus' - Finished in state Completed()
23:39:08.809 | INFO    | Flow run 'sparkling-mandrill' - PrefectHQ/prefect repository statistics 🤓:
23:39:08.810 | INFO    | Flow run 'sparkling-mandrill' - Stars 🌠 : 12147
23:39:08.811 | INFO    | Flow run 'sparkling-mandrill' - Forks 🍴 : 1245
23:39:08.812 | INFO    | Flow run 'sparkling-mandrill' - Average commits per contributor 💌 : 344.47
23:39:08.957 | INFO    | Flow run 'sparkling-mandrill' - Finished in state Completed('All states completed.')
```
</div>

With subflows, you easily have coupled workflows in just a few lines!

