# Orchestration Quickstart

This guide is desinged to get you to the point of successfully deploying a Prefect flow in as few steps as possible. For a more comprhensive introduction to Prefect's concepts and approach to orchestration, please follow our [tutorial pages](/tutorial/index/).

### Step 1: [Install Prefect](/getting-started/installation/)

We recommend installing Prefect using a Python virtual environment manager such as pipenv, conda, or virtualenv/venv.

```bash 
pip install -U prefect
```
### Step 2: Connect to Cloud or Self Host Prefect Server
[Create a forever free cloud accoun](/cloud/cloud-quickstart) and authenticate via your terminal by running:
```bash
prefect cloud login -k <your API key>
```
OR to use our open source offering, in a new terminal run
```bash
prefect server start
```

### Step 3: Author a Flow
Clone a test repo in GitHub or equivalent and get started by by **adding an `@flow` decorator to any python function**. This is the fastest way to get started with Prefect.

!!! Tip "Reminder"
    - At a minimum you need to define at least one flow function, tasks are optional but add more granular observability and added orchestration functionality.
    - Flows can be called inside of other flows, we call these subflows, but a task cannot contain task or flow calls as a task represents a discrete unit of python logic.

Here is an example flow that contains two task calls in a script called `my_flow.py`:

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
        contributors = get_contributors(contributors_url)
        average_commits = calculate_average_commits(contributors)
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
Prefect flows don't just look pythonic, they run like python function too. 

Call the function that you've decorated with the `@flow` decorator to see a local instance of a FlowRun.

```bash
python my_flow.py
``` 

#### TODO: Update the terminal output
<div class="terminal">
```bash
15:27:42.543 | INFO    | prefect.engine - Created flow run 'olive-poodle' for flow 'my-favorite-function'
15:27:42.543 | INFO    | Flow run 'olive-poodle' - Using task runner 'ConcurrentTaskRunner'
What is your favorite number?
15:27:42.652 | INFO    | Flow run 'olive-poodle' - Finished in state Completed()
42
```
</div>


In addition to seeing these logs, you can also checkout out the flow run from the UI to see its dependecy diagram. Just head to the flow runs dashboard.

Local execution is great for development and testing, but for productionized execution and scheduling you'll want to deploy your flow.


### Step 5: Deploy Flow

!!! warning "Warning"
    Before running any `prefect deploy` or `prefect init` commands, double check that you are at the **root of your repo**, otherwise the Prefect Worker may struggle to get to the same entrypoint during remote execution!

```bash
prefect deploy my_flow.py:my_flow_function
```

Now that you have run the deploy command, the CLI will prompt you through different options you can set with your deployment. 🧙 Follow the wizard to name your deployment, add an optional schedule, create a Work Pool, and optionally configure a flow code pull step.

!!! note "CLI Note"
    The above deployment command follows the following format `prefect deploy entrypoint` that you can use to deploy your flows in the future. It will always be relative to the root of your repo:
    
    `prefect deploy path_to_flow/my_flow_file.py:name_of_flow_function`


### Step 6: Start a Worker and Run Deployed Flow

A worker should be started to poll the Work Pool created when you build your deployment. In a new terminal run:

```bash
prefect worker start --pool <name-of-your-work-pool>
```

Now that your worker is started, you are ready to kick off deployed flow runs from either the UI or by running:

```bash
prefect deployment run <my-flow-name>/<my-deployment-name>
```

For more information see tutorials or guides.