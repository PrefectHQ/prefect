# Orchestration Quickstart

This guide is designed to get you to the point of successfully deploying a Prefect flow in as few steps as possible. For a more comprehensive introduction to Prefect's core orchestration concepts, please follow our [tutorial pages](/tutorial/index/).

### Step 1: [Install Prefect](/getting-started/installation/)

We recommend installing Prefect using a Python virtual environment manager such as conda, or virtualenv.

```bash 
pip install -U prefect
```
### Step 2: Connect to Cloud or Self Host Prefect Server
[Create a forever free cloud account](/cloud/cloud-quickstart) and authenticate to your workspace via your terminal by running:
```bash
prefect cloud login
```
OR to use our open source offering, in a new terminal run to host the Prefect engine locally.
```bash
prefect server start
```

### Step 3: Author a Flow
**The fastest way to get started with Prefect is to clone a test repo in GitHub or equivalent and simply add an `@flow` decorator to any python function**.

!!! Tip "Quick Tips"
    - At a minimum you need to define at least one flow function.
    - Your flows can be segmented by introducing task (`@task`) functions, which can be invoked from within these flows.
    - A task represents a discrete unit of Python logic whereas Flows are more akin to parent functions that can accommodate a broad range of workflow logic.
    - Flows can be called inside of other flows (we call these subflows) but a task **cannot** be run inside of another task or from outside the context of a flow.

Here is an example flow that contains two task calls in a script called `my_flow.py`:

##### TODO: Improve Code Example

```python
import httpx
from prefect import flow, task

@task(retries=3)
def get_contributors(url):
    response = httpx.get(url)
    if response.status_code == 200:
        contributors = response.json()
        return len(contributors)
    else:
        raise Exception('Failed to fetch contributors.')

@task(retries=4)
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

@flow(name="Repo Info", log_prints=True)
def my_flow_function():
    url = 'https://api.github.com/repos/PrefectHQ/prefect'
    api_response = httpx.get(url)
    if api_response.status_code == 200:
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
    else:
        raise Exception('Failed to fetch repository information.')

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

Local execution is great for development and testing, but in order to schedule flow runs or trigger them based on events, you’ll need to [deploy](/tutorial/deployments/) them.


### Step 5: Deploy Flow

Deploying your flows is, in essence, the act of informing the Prefect API of where, how, and when to run your flows. Prefect offers CLI commands for quick deployment creation.

!!! warning "Warning"
    Before running any `prefect deploy` or `prefect init` commands, double check that you are at the **root of your repo**, otherwise the Prefect Worker may struggle to get to the same entrypoint during remote execution!

When you run the deploy command, the CLI will prompt you through different options you can set with your deployment. 🧙 Follow the wizard to name your deployment, add an optional schedule, create a Work Pool, and optionally configure a flow code pull step.

```bash
prefect deploy my_flow.py:my_flow_function
```
!!! Tip "Process Type Work Pool Recommended:"
    A `process` type WorkPool is the simplist option for local execution and is reccomended for beginners.

!!! note "CLI Note"
    The above deployment command follows the following format `prefect deploy entrypoint` that you can use to deploy your flows in the future. It will always be relative to the root of your repo:
    
    `prefect deploy path_to_flow/my_flow_file.py:name_of_flow_function`


### Step 6: Start a Worker and Run Deployed Flow

A worker should be started to poll the Work Pool created when you defined your deployment. In a new terminal run:

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

### Next Steps

- Learn about deploying multiple flows and CI/CD with our [`prefect.yaml`](/concepts/projects/#the-prefect-yaml-file)
- Check out some of our other [work pools](/concepts/work-pools/)
- [Our Concepts](/concepts/) contain deep dives into Prefect components.
- [Guides](/guides/) provide step by step recipes for common Prefect operations including:
    - [Deploying on Kubernetes](/guides/deployment/helm-worker/)
    - [Deploying flows in Docker](/guides/deployment/docker/)
    - [Writing tests](/guides/testing)
And more!