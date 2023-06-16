# Deployment Quickstart

### Step 1: Install Prefect

We recommend installing Prefect using a Python virtual environment manager such as pipenv, conda, or virtualenv/venv.

The following sections describe how to install Prefect in your development or execution environment.

Installing the latest version
Prefect is published as a Python package. To install the latest Prefect release, run the following in a shell or terminal session:

```bash 
pip install -U prefect
```
### Step 2: Authenticate to Prefect Cloud or Start Server
Create a forever free cloud account and authenticate via your terminal by running:
```bash
prefect cloud login -k <your API key>
```
OR to use our open source offering, in a new terminal run
```bash
prefect server start
```

### Step 3: Author a Flow
Clone a test repo in GitHub or equivalent and write your Prefect Flow by adding an `@flow` decorator to any python function.

!!! reminder "Remember:"
    - At a minimum you need to define at least one flow function, tasks are optional but add granularity and added functionality.
    - Flows can be called inside of other flows, we call these subflows, but a task cannot contain task or flow calls as a task represents a discrete unit of python logic.

Here is an example flow script called `my_flow.py`:

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

if __name__ == '__main__':
    get_repo_info()
```

### Step 4: Run your Flow Locally
```bash
python my_flow.py
``` 

### Step 5: Deploy Flow

!!! warning "Warning:"
    Before running any `prefect deploy` or `prefect init` commands, double check that you are at the **top/root/base of your repo**, otherwise the worker may struggle to get to the same entrypoint during remote execution!

```bash
prefect deploy my_flow.py:get_repo_info
```

!!! note "CLI Note:"
    The above deployment command follows the following format `prefect deploy entrypoint` that you can use to deploy your flows in the future:
    
    `prefect deploy my_flow.py:get_repo_info`

Now that you have run the deploy command, the CLI will prompt you through different options you can set with your deployment. 🧙 Follow the wizard to name your deployment and select or create a Work Pool among other optional steps.  

### Step 6: Start a Worker and Run Deployed Flow

```bash
prefect worker start --pool <name-of-your-work-pool>
```

Now that your worker is started, you are ready to kick off deployed flow runs from either the UI or by running:

```bash
prefect deployment run <my-flow-name>/<my-deployment-name>
```
