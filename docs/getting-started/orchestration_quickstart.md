# Orchestration Quickstart

This guide is designed to show you how to deploy a Prefect flow in as few steps as possible. For a more comprehensive introduction to Prefect's core components and how they work together, please follow our [tutorial](/tutorial/index/).

### Prerequisites

1. Before you start, make sure you have [prefect installed](/getting-started/installation) and are [connected to a Prefect server instance](getting-started/first_steps/#connect-to-prefects-api/). 
2. Optional: Prefect integrates well with version control platforms like GitHub and equivalent. Before you deploy your flow, consider pushing your flow code to a remote repo.

### Step 1: Author a Flow
**The fastest way to get started with Prefect is to add a `@flow` decorator to any python function**.

!!! Tip "Quick Tips"
    - At a minimum, you need to define at least one flow function.
    - Your flows can be segmented by introducing task (`@task`) functions, which can be invoked from within these flows.
    - A task represents a discrete unit of Python code, whereas flows are more akin to parent functions accommodating a broad range of workflow logic.
    - Flows can be called inside of other flows (we call these subflows) but a task **cannot** be run inside of another task or from outside the context of a flow.

Here is an example flow that calls 2 tasks:
```python
# my_flow.py
import httpx
from prefect import flow, task

@task # This is a Task!
def get_contributors(url):
    response = httpx.get(url)
    response.raise_for_status()
    contributors = response.json()
    return {"n_contributors": len(contributors)}

@task(retries=4) # This is a Task that will retry 4 times!
def calculate_average_commits(contributors):
    commits_url = f'https://api.github.com/repos/PrefectHQ/prefect/stats/contributors'
    response = httpx.get(commits_url)
    response.raise_for_status()
    commit_data = response.json()
    total_commits = sum(c['total'] for c in commit_data)
    average_commits = total_commits / contributors["n_contributors"]
    return average_commits

@flow(name="Repo Info", log_prints=True) # This is a Flow called Repo Info
def my_flow_function():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    api_response.raise_for_status()
    repo_info = api_response.json()
    stars = repo_info['stargazers_count']
    forks = repo_info['forks_count']
    contributors_url = repo_info['contributors_url']
    contributors = get_contributors(contributors_url) # Task Call
    average_commits = calculate_average_commits(contributors) # Task Call
    print(f"PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {stars}")
    print(f"Forks 🍴 : {forks}")
    print(f"Average commits per contributor 💌 : {average_commits:.2f}")

if __name__ == '__main__':
    my_flow_function() # Call a flow function for a local flow run!
```

### Step 2: Run your Flow locally
Prefect flows don't just look pythonic, they run like python functions too! 

Call any function that you've decorated with a `@flow` decorator to see a local instance of a flow run.

```bash
python my_flow.py
``` 

<div class="terminal">
```bash
14:36:55.567 | INFO    | prefect.engine - Created flow run 'dazzling-hawk' for flow 'Repo Info'
14:36:55.570 | INFO    | Flow run 'dazzling-hawk' - View at https://app.prefect.cloud/account/0ff44498-d380-4d7b-bd68-9b52da03823f/workspace/aaf96bd2-298c-4fe4-98b0-6b4d520951e1/flow-runs/flow-run/5a891994-8ac3-44e5-894a-1b2f801c9333
14:36:56.497 | INFO    | Flow run 'dazzling-hawk' - Created task run 'get_contributors-0' for task 'get_contributors'
14:36:56.499 | INFO    | Flow run 'dazzling-hawk' - Executing 'get_contributors-0' immediately...
14:36:57.405 | INFO    | Task run 'get_contributors-0' - Finished in state Completed()
14:36:57.525 | INFO    | Flow run 'dazzling-hawk' - Created task run 'calculate_average_commits-0' for task 'calculate_average_commits'
14:36:57.526 | INFO    | Flow run 'dazzling-hawk' - Executing 'calculate_average_commits-0' immediately...
14:36:58.227 | INFO    | Task run 'calculate_average_commits-0' - Finished in state Completed()
14:36:58.256 | INFO    | Flow run 'dazzling-hawk' - PrefectHQ/prefect repository statistics 🤓:
14:36:58.257 | INFO    | Flow run 'dazzling-hawk' - Stars 🌠 : 12160
14:36:58.258 | INFO    | Flow run 'dazzling-hawk' - Forks 🍴 : 1252
14:36:58.259 | INFO    | Flow run 'dazzling-hawk' - Average commits per contributor 💌 : 345.07
14:36:58.494 | INFO    | Flow run 'dazzling-hawk' - Finished in state Completed('All states completed.')
```
</div>


You'll find a link directing you to the flow run page conveniently positioned at the top of your flow logs.
![Alt text](flow_run_diagram.png)

Local flow run execution is great for development and testing, but in order to schedule flow runs or trigger them based on events, you’ll need to [deploy](/tutorial/deployments/) your flows.


### Step 3: Deploy the flow

Deploying your flows is, in essence, the act of informing the Prefect API of where, how, and when to run your flows.

!!! warning "Always run `prefect deploy` commands from the **root** level of your repo!"

When you run the `deploy` command, Prefect will automatically detect any flows defined in your repository. Select the one you wish to deploy. Then, follow the 🧙 wizard to name your deployment, add an optional schedule, create a work pool, optionally configure remote flow code storage, and more!

```bash
prefect deploy
```

!!! note "It's recommended to save the configuration for the deployment."
    Saving the configuration for your deployment will result in a `prefect.yaml` file populated with your first deployment. You can use this yaml file to edit and [define multiple deployments](/concepts/deployments-ux/) for this repo.
### Step 4: Start a Worker and Run Deployed Flow

Start a worker to manage local flow execution. Each worker polls its assigned [work pool](/tutorial/deployments/#why-work-pools-and-workers).

In a new terminal, run:
```bash
prefect worker start --pool '<work-pool-name>'
```

Now that your worker is started, you are ready to kick off deployed flow runs from either the UI or by running:

```bash
prefect deployment run '<flow-name>/<deployment-name>'
```

Congrats on your first successfully deployed flow run! 🎉

Now you've seen:

- how to define your flows and tasks using decorators
- how to deploy a flow
- how to start a worker

### Next Steps

- Learn about deploying multiple flows and CI/CD with [`prefect.yaml`](/concepts/projects/#the-prefect-yaml-file)
- Check out some of our other [work pools](/concepts/work-pools/)
- [Our concepts](/concepts/) contain deep dives into Prefect components.
- [Guides](/guides/) provide step by step recipes for common Prefect operations including:
    - [Deploying on Kubernetes](/guides/deployment/helm-worker/)
    - [Deploying flows in Docker](/guides/deployment/docker/)