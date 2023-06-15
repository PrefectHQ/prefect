# Deployment Quickstart

### Step 1: Install Prefect

We recommend installing Prefect using a Python virtual environment manager such as pipenv, conda, or virtualenv/venv.

The following sections describe how to install Prefect in your development or execution environment.

Installing the latest version
Prefect is published as a Python package. To install the latest Prefect release, run the following in a shell or terminal session:

```bash 
pip install -U prefect
```

### Step 2: Author a Flow
Clone a test repo in GitHub or equivalent and write your Prefect Flow:
`my_flow.py`
```python
import httpx
from prefect import flow

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
@task(retries=3)
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

### Step 3: Deploy Flow

!!! Warning "Warning:"
    Ensure that you run the prefect deploy command from the **top/root/base of your repo**, otherwise the worker may struggle to get to the same entrypoint during remote execution.

```bash
prefect deploy path_to_flow_file/my_flow.py:get_repo_info
```