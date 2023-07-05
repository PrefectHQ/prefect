# Orchestration Quickstart

This guide is designed to get you to the point of successfully running a deployed Prefect flow in as few steps as possible. For a more comprehensive introduction to Prefect's core orchestration concepts, please follow our [tutorial](/tutorial/index/).

### Step 1: [Install Prefect](/getting-started/installation/)

We recommend installing Prefect using a Python virtual environment manager such as conda or virtualenv.

```bash 
pip install -U prefect
```
### Step 2: Connect to Cloud or Self Host Prefect Server
[Create a forever free cloud account](/cloud/cloud-quickstart) and authenticate to your workspace via your terminal by running:
```bash
prefect cloud login
```
If you'd instead like to use our open source offering, host the Prefect engine locally by running
```bash
prefect server start
```

### Step 3: Author a Flow
**The fastest way to get started with Prefect is to clone a test repo in GitHub or equivalent and simply add an `@flow` decorator to any python function**.

!!! Tip "Quick Tips"
    - At a minimum, you need to define at least one flow function.
    - Your flows can be segmented by introducing task (`@task`) functions, which can be invoked from within these flows.
    - A Task represents a discrete unit of Python logic whereas Flows are more akin to parent functions accommodating a broad range of workflow logic.
    - Flows can be called inside of other flows (we call these subflows) but a task **cannot** be run inside of another task or from outside the context of a flow.

Here is an example flow that calls 2 tasks:

```python
# my_flow.py
import httpx
from prefect import flow, task

@task(retries=3)
def get_contributors(url):
    response = httpx.get(url)
    response.raise_for_status()  # Will raise an httpx.HTTPStatusError if the request fails
    contributors = response.json()
    return len(contributors)

@task(retries=4)
def calculate_average_commits(contributors):
    commits_url = f'https://api.github.com/repos/PrefectHQ/prefect/stats/contributors'
    response = httpx.get(commits_url)
    response.raise_for_status()  # Will raise an httpx.HTTPStatusError if the request fails
    commit_data = response.json()
    total_commits = sum(c['total'] for c in commit_data)
    average_commits = total_commits / contributors
    return average_commits

@flow(name="Repo Info", log_prints=True)
def my_flow_function():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    api_response.raise_for_status()  # Will raise an httpx.HTTPStatusError if the request fails
    repo_info = api_response.json()
    stars = repo_info['stargazers_count']
    forks = repo_info['forks_count']
    contributors_url = repo_info['contributors_url']
    contributors = get_contributors(contributors_url) # Task Call Here
    average_commits = calculate_average_commits(contributors) # Task Call Here
    print(f"PrefectHQ/prefect repository statistics 🤓:")
    print(f"Stars 🌠 : {stars}")
    print(f"Forks 🍴 : {forks}")
    print(f"Average commits per contributor 💌 : {average_commits:.2f}")

if __name__ == '__main__':
    my_flow_function()
```

### Step 4: Run your Flow Locally
Prefect Flows don't just look pythonic, they run like python functions too! 

Call any function that you've decorated with a `@flow` decorator to see a local instance of a FlowRun.

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


Beyond examining these logs, you have the option to explore the FlowRun via the UI to visualize its dependency diagram. You should find a link directing you to the FlowRun page conveniently positioned at the top of your flow logs.

Local execution is great for development and testing, but in order to schedule flow runs or trigger them based on events, you’ll need to [deploy](/tutorial/deployments/) your flows.


### Step 5: Deploy Flow

Deploying your flows is, in essence, the act of informing the Prefect API of where, how, and when to run your flows. Prefect offers CLI commands for quick deployment creation.

!!! warning "Run `prefect deploy` commands from the **root** of your repo!"
    When running any `prefect deploy` or `prefect init` commands, double check that you are at the root of your repo, otherwise the worker may attempt to use an incorrect flow entrypoint during remote execution!

When you execute the deploy command, Prefect will automatically detect any flows defined in your repository. Simply choose the one you wish to deploy. Then, follow the 🧙 wizard to name your deployment, add an optional schedule, create a Work Pool, optionally configure a flow code pull step, and more!

```bash
prefect deploy
```
The last prompt in the `prefect deploy` wizard asks if you would like to save the configuration for the deployment, saying yes to this will result in a prefect.yaml file populated with your first deployment. You can use this yaml file to edit and [manage all deployments](/concepts/deployments-ux/) for this repo.

### Step 6: Start a Worker and Run Deployed Flow

Since Prefect's API does not directly execute flows, you'll need to start a worker to manage local flow execution. [Each worker polls its assigned WorkPool](https://docs.prefect.io/2.10.18/tutorial/deployments/#why-work-pools-and-workers).

In a new terminal run:
```bash
prefect worker start --pool <name-of-your-work-pool>
```

Now that your worker is started, you are ready to kick off deployed flow runs from either the UI or by running:

```bash
prefect deployment run 'Repo Info/<my-deployment-name>'
```

!!! reminder "Reminder: A flow name can be different from its function name!"
    The above deployment run command follows the following format:
    
    `prefect deployment run '<flow name>/<deployment-name>`

!!! Warning "Common Pitfall"
    If you optionally set a git based pull step, ensure that you have pushed any changes to your flow script to your GitHub repo - at any given time, your worker will pull the code that exists there!

Congrats on your first successfully deployed FlowRun! Now you've seen how to define your flows and tasks using decorators, how to deploy a flow, and how to start a worker.

### Next Steps

- Learn about deploying multiple flows and CI/CD with our [`prefect.yaml`](/concepts/projects/#the-prefect-yaml-file)
- Check out some of our other [work pools](/concepts/work-pools/)
- [Our Concepts](/concepts/) contain deep dives into Prefect components.
- [Guides](/guides/) provide step by step recipes for common Prefect operations including:
    - [Deploying on Kubernetes](/guides/deployment/helm-worker/)
    - [Deploying flows in Docker](/guides/deployment/docker/)
    - [Writing tests](/guides/testing)
And more!