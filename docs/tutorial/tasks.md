---
description: Adding tasks to our flows
tags:
    - tutorial
    - tasks
---

Prefect tasks are a fundamental component of Prefect's workflow orchestration framework. While flows provide a high-level structure for organizing and executing your code, tasks add another atomic component that can be orchestrated and observed within the context of a flow. 

!!! tip "Tasks cannot be called from other tasks directly, but they enable concurrency, allowing you to execute multiple tasks concurrently. This concurrency can greatly enhance the efficiency and performance of your workflows."

To demonstrate the usage of tasks, let's modify our existing flow by adding some tasks. 

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
@task()
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

Now run your flow in the terminal

Locally we'll see something like this: 
<div class="terminal">
```bash
13:04:19.212 | INFO    | prefect.engine - Created flow run 'invisible-millipede' for flow 'get-repo-info'
13:04:19.220 | INFO    | Flow run 'invisible-millipede' - View at https://app.prefect.cloud/account/0ff44498-d380-4d7b-bd68-9b52da03823f/workspace/f579e720-7969-4ab8-93b7-2dfa784903e6/flow-runs/flow-run/2b45a6c8-0103-422f-957a-ca85f3187234
13:04:20.194 | INFO    | Flow run 'invisible-millipede' - Created task run 'get_contributors-0' for task 'get_contributors'
13:04:20.196 | INFO    | Flow run 'invisible-millipede' - Executing 'get_contributors-0' immediately...
13:04:20.916 | INFO    | Task run 'get_contributors-0' - Finished in state Completed()
13:04:21.039 | INFO    | Flow run 'invisible-millipede' - Created task run 'calculate_average_commits-0' for task 'calculate_average_commits'
13:04:21.040 | INFO    | Flow run 'invisible-millipede' - Executing 'calculate_average_commits-0' immediately...
13:04:22.387 | INFO    | Task run 'calculate_average_commits-0' - Finished in state Completed()
13:04:22.394 | INFO    | Flow run 'invisible-millipede' - PrefectHQ/prefect repository statistics 🤓:
13:04:22.394 | INFO    | Flow run 'invisible-millipede' - Stars 🌠 : 12146
13:04:22.395 | INFO    | Flow run 'invisible-millipede' - Forks 🍴 : 1245
13:04:22.395 | INFO    | Flow run 'invisible-millipede' - Average commits per contributor 💌 : 344.43
13:04:22.532 | INFO    | Flow run 'invisible-millipede' - Finished in state Completed('All states completed.')
```

If we click the link in our terminal and follow it to Prefect Cloud, we'll see something like this:


![Tasks provide greater visibility as well as concurrency](/img/tutorial/cloud-flow-run.png)


By encapsulating a specific unit of work within a task, you can define its inputs, outputs, and behavior. This modular approach allows for easier management and composition of complex workflows.

For example, you can create a task that makes a network call to an external API and retrieves data. This task can then be orchestrated alongside other tasks within the flow, providing a clear structure to our workflow.

Flows and tasks share some common features. Both have metadata attributes such as name, description (which can be in full markdown format), and tags. They also support type-checked parameters, allowing you to define the expected data types of inputs and outputs. Additionally, both flows and tasks provide functionality for retries, timeouts, and other hooks to handle failure and completion events. This overlap in functionality ensures consistency and flexibility in managing your workflows.

Some examples of task features include:

- Concurrency
- Caching
- Parallelism
- Concurrency Limits
- Tagging
- Retries
- Advanced dependency management

When to use tasks vs flows?

By separating network calls between tasks Prefect can most effectively