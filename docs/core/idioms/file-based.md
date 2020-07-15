# Using file based flow storage

As of Prefect version `0.12.5` all storage options support storing flows as files. This means that flow code can change in between (or even during) runs without needing to be reregistered. As long as the structure of the flow itself does not change, only the task content, then a Prefect API backend will be able to execute the flow. This is a useful storage mechanism especially for testing, debugging, CI/CD processes, and more!

### Enable file storage

GitHub storage only supports files however the other storage options (Local, Docker, S3, etc.) store
flows both as pickles and files. To switch to using file storage and enable the workflow above set
`stored_as_script=True` on the storage object.

### Example file based workflow

::: warning GitHub dependency
This idiom requires that `git` is installed as well as Prefect's `github` extra dependencies:

```bash
pip install 'prefect[github]'
```
:::

In this example we will walk through a potential workflow you may use when registering flows with [GitHub](/api/latest/environments/storage.html#github) storage. This example takes place in a GitHub repository with the following structure:

```
repo
    README.md
    flows/
        my_flow.py
```

First, compose your flow file and give the flow `GitHub` storage:

```python
# flows/my_flow.py

from prefect import task, Flow
from prefect.environments.storage import GitHub

@task
def get_data():
    return [1, 2, 3, 4, 5]

@task
def print_data(data):
    print(data)

with Flow("file-based-flow") as flow:
    data = get_data()
    print_data(data)

flow.storage = GitHub(
    repo="org/repo",                 # name of repo
    path="flows/my_flow.py",        # location of flow file in repo
    secrets=["GITHUB_ACCESS_TOKEN"]  # name of personal access token secret
)
```

Here's a breakdown of the three kwargs set on the `GitHub` storage:

- `repo`: the name of the repo that this code will live in
- `path`: the location of the flow file in the repo. This must be an exact match to the path of the file.
- `secrets`: the name of a [default Prefect secret](/core/concepts/secrets.html#default-secrets) which is a GitHub [personal access token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line). This is set so that when the flow is executed it has the proper permissions to pull the file from the repo.

Push this code to the repository:

```bash
git add .
git commit -m 'Add my flow'
git push
```

Now that the file exists on the repo the flow needs to be registered with a Prefect API backend (either Core's server or Prefect Cloud).

```bash
prefect register flow -f flows/my_flow.py
Result check: OK
Flow: http://localhost:8080/flow/9f5f7bea-186e-44d1-a746-417239663614
```

The flow is ready to run! Every time you need to change the code inside your flow's respective tasks all you need to do is commit that code to the same location in the repository and each subsequent run will use that code.

::: warning Flow Structure
If you change any of the structure of your flow such as task names, rearrange task order, etc. then you will need to reregister that flow.
:::


### File based Docker storage

```python
flow.storage = Docker(
    path="my_flow.py",
    files={"/source/of/my_flow.py": "my_flow.py"},
    stored_as_file=True
)
```

To store flows as files in Docker storage three kwargs needs to be set:

- `path`: pointing to the path that the file is stored in the Docker image
- `files`: a dictionary of local file source to path destination in image
- `stored_as_file`: boolean opting into file based storage
