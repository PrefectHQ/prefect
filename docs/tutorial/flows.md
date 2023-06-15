---
description: Learn the basics of creating and running Prefect flows and tasks.
tags:
    - tutorial
    - getting started
    - basics
    - tasks
    - flows
    - subflows
---
## What is a flow?

A [flow](concepts/flows/) is the basis of all Prefect workflows. A flow is a Python function decorated with a `@flow` decorator.

Some important points about flows:

1. All Prefect workflows are defined within the context of a flow.
2. Every Prefect workflow must contain at least one `flow` function that serves as the entrypoint for execution of the flow.
3. Flows can include calls to tasks as well as to child flows, which we call "subflows" in this context. At a high level, this is just like writing any other Python application: you organize specific, repetitive work into tasks, and call those tasks from flows.

The simplest way to begin with Prefect is to import `flow` and annotate your Python function using the `[@flow](https://docs.prefect.io/2.10.13/api-ref/prefect/flows/#prefect.flows.flow)` decorator.

```python
import httpx
from prefect import flow

@flow # <--- This is a flow decorator!
def get_repo_info():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    if api_response.status_code == 200:
        repo_info = api_response.json()
        stars = repo_info['stargazers_count']
        forks = repo_info['forks_count']
        contributors_url = repo_info['contributors_url']
        print(f"PrefectHQ/prefect repository statistics 🤓:")
        print(f"Stars 🌠 : {stars}")
        print(f"Forks 🍴 : {forks}")
    else:
        raise Exception('Failed to fetch repository information.')

if __name__ == '__main__':
    get_repo_info()
```
If you run this flow in your terminal you will see some interesting output:
<div class="terminal">
```bash
12:47:42.792 | INFO    | prefect.engine - Created flow run 'ludicrous-warthog' for flow 'get-repo-info'
12:47:42.832 | INFO    | Flow run 'ludicrous-warthog' - View at https://app.prefect.cloud/account/0ff44498-d380-4d7b-bd68-9b52da03823f/workspace/f579e720-7969-4ab8-93b7-2dfa784903e6/flow-runs/flow-run/d15662f9-f959-4c1a-9a01-fc99fe302241
PrefectHQ/prefect repository statistics 🤓:
Stars 🌠 : 12146
Forks 🍴 : 1245
12:47:45.008 | INFO    | Flow run 'ludicrous-warthog' - Finished in state Completed()
```
</div>
## What can you do with flows?

### Retries

Organizing your workflow code into smaller flow and task units lets you take advantage of Prefect features like retries. It helps provide for additional ways to respond on how your workflows fail, and offer more control on fail safe options for your workflow.

*Potentially insert code example? It might be redundant

### Subflow

Not only can you call task functions within a flow, but you can also call other flow functions! Child flows are called [subflows](https://docs.prefect.io/concepts/flows/#composing-flows) and allow you to efficiently manage, track, and version common multi-task logic.

```python

import httpx
from prefect import flow, task


@flow(log_prints = True)
def get_repo_info():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    if api_response.status_code == 200:
        repo_info = api_response.json()
        stars = repo_info['stargazers_count']
        forks = repo_info['forks_count']
        contributors_url = repo_info['contributors_url']
        average_commits = calculate_average_commits(contributors_url)
        print(f"PrefectHQ/prefect repository statistics 🤓:")
        print(f"Stars 🌠 : {stars}")
        print(f"Forks 🍴 : {forks}")
        print(f"Average commits per contributor 💌 : {average_commits:.2f}")
    else:
        raise Exception('Failed to fetch repository information.')
    
@flow()
def calculate_average_commits(contributors_url):
    response = httpx.get(contributors_url)
    if response.status_code == 200:
        contributors = len(response.json())
    else:
        raise Exception('Failed to fetch contributors.')      
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

### Next Steps

To recap, simply adding an @flow decorator will convert a python function into an observed workflow. This pattern is coupled with a responsive user interface and fine tune orchestration features that are easy to add and quick to develop with.

On the next guide, we will showcase how to use tasks to in order to supercharge this github example even further and to help organize your complex workflows.