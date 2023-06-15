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

A [flow](/concepts/flows/) is the basis of all Prefect workflows. A flow is a Python function decorated with a `@flow` decorator.

Some important points about flows:

1. All Prefect workflows are defined within the context of a flow.
2. Every Prefect workflow must contain at least one `flow` function that serves as the entrypoint for execution of the flow.
3. Flows can include calls to tasks as well as to child flows, which we call "subflows" in this context. At a high level, this is just like writing any other Python application: you organize specific, repetitive work into tasks, and call those tasks from flows.

The simplest way get started with Prefect is to import `flow` and annotate your Python function using the [@flow](/api-ref/prefect/flows/#prefect.flows.flow) decorator.

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

It helps provide for additional ways to respond on how your workflows fail, and offer more control on fail safe options for your workflow.


The flow decorator lets you specify the number of retries.

### Next Steps

To recap, simply adding an @flow decorator will convert a python function into an observed workflow. This pattern is coupled with a responsive user interface and fine tune orchestration features that are easy to add and quick to develop with.

On the next guide, we will showcase how to use tasks to in order to supercharge this github example even further and to help organize your complex workflows.