# Using script based flow storage

As of Prefect version `0.12.5` all storage options support storing flows as
source files instead of pickled objects. This means that flow code can change
in between (or even during) runs without needing to be reregistered. As long as
the structure of the flow itself does not change, only the task content, then a
Prefect API backend will be able to execute the flow. This is a useful storage
mechanism especially for testing, debugging, CI/CD processes, and more!

### Enable script storage

Some storage classes (e.g. `GitHub`, `GitLab`, `Bitbucket`, ...) only support
script based storage. All other classes require you to opt-in by passing
`stored_as_script=True` to the storage class constructor.

### Example script based workflow

::: warning GitHub dependency
This idiom requires that `git` is installed as well as Prefect's `github` extra dependencies:

```bash
pip install 'prefect[github]'
```
:::

In this example we will walk through a potential workflow you may use when registering flows with
[GitHub](/api/latest/storage.html#github) storage. This example takes place in a GitHub
repository with the following structure:

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
from prefect.storage import GitHub

@task
def get_data():
    return [1, 2, 3, 4, 5]

@task
def print_data(data):
    print(data)

with Flow("example") as flow:
    data = get_data()
    print_data(data)

flow.storage = GitHub(
    repo="org/repo",                            # name of repo
    path="flows/my_flow.py",                    # location of flow file in repo
    access_token_secret="GITHUB_ACCESS_TOKEN"   # name of personal access token secret
)
```

Here's a breakdown of the three kwargs set on the `GitHub` storage:

- `repo`: the name of the repo that this code will live in
- `path`: the location of the flow file in the repo. This must be an exact match to the path of the file.
- `access_token_secret`: If your flow is stored in a private repo, you'll need
  to provide credentials to access the repo. This takes the name of a
  [Prefect secret](/core/concepts/secrets.html) which contains a GitHub
  [personal access token](https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line).

Push this code to the repository:

```bash
git add .
git commit -m 'Add my flow'
git push
```

Now that the file exists on the repo the flow needs to be registered with a Prefect API backend (either
Core's server or Prefect Cloud).

```bash
$ prefect register -p flows/my_flow.py --project MyProject
Collecting flows...
Processing 'flows/my_flow.py':
  Building `GitHub` storage...
  Registering 'example'... Done
  └── ID: c0dabf5a-4234-431b-8cc1-dbb6f3d6546d
  └── Version: 1
======================== 1 registered ========================
```

The flow is ready to run! Every time you need to change the code inside your flow's respective tasks all
you need to do is commit that code to the same location in the repository and each subsequent run will
use that code.

::: warning Flow Structure
If you change any of the structure of your flow such as task names, rearrange task order, etc. then you
will need to reregister that flow.
:::

::: tip GitLab users
This example applies to GitLab as well. To use GitLab storage, install the `gitlab` extra:

```bash
pip install 'prefect[gitlab]'
```

You can replace `GitHub` instances in the example above with `GitLab`, use the `"GITLAB_ACCESS_TOKEN"` secret rather than `"GITHUB_ACCESS_TOKEN"`, and then you may run the example as written.
:::

:::tip Bitbucket users
Similarly, to use Bitbucket (Server only) based storage, install the `bitbucket` extra:

```bash
pip install 'prefect[bitbucket]'
```

Bitbucket storage also operates largely the same way. Replace `GitHub` with `Bitbucket` and use the `BITBUCKET_ACCESS_TOKEN` secret.  However, Bitbucket requires an additional argument: `project`.  The `flow.storage` in the above example would be declared as follows for Bitbucket storage:

```python
flow.storage = Bitbucket(
    project="project",                              # name of project that repo resides in
    repo="org/repo",                                # name of repo
    path="flows/my_flow.py",                        # location of flow file in repo
    access_token_secret="BITBUCKET_ACCESS_TOKEN"    # name of personal access token secret
)
```
:::

### Script based Docker storage

```python
flow.storage = Docker(
    path="my_flow.py",
    files={"/source/of/my_flow.py": "my_flow.py"},
    stored_as_script=True
)
```

To store flows as files in Docker storage three kwargs needs to be set if you are using Prefect's default
Docker storage build step:

- `path`: the path that the file is stored in the Docker image
- `files`: a dictionary of local file source to path destination in image
- `stored_as_script`: boolean enabling script based storage

If your Docker storage is using an image that already has your flow files added into it then you only
need to specify the following:

```python
flow.storage = Docker(
    path="/location/in/image/my_flow.py",
    stored_as_script=True
)
```

### Script based cloud storage

Script based storage of flows is also supported for flows stored in S3 and GCS buckets. The following
snippet shows S3 and GCS storage options where a flow is stored as a script and the `key` points to the
specific file path in the bucket.

```python
flow.storage = S3(
    bucket="my-flow-bucket",
    stored_as_script=True,
    key="flow_path/in_bucket.py"
)

# or

flow.storage = GCS(
    bucket="my-flow-bucket",
    stored_as_script=True,
    key="flow_path/in_bucket.py"
)
```

Storing flows this way is similar to the git-based flow storage where users manually have to upload the
flows to the buckets and then set a key to match. There is another option where flows scripts can be
automatically uploaded to the buckets by providing a file path to the storage object. (Note: if `key` is
not set then a key will be automatically generated for the storage of the flow)

```python{4,12}
flow.storage = S3(
    bucket="my-flow-bucket",
    stored_as_script=True,
    local_script_path="my_flow.py"  # Local file that you want uploaded to the bucket
)

# or

flow.storage = GCS(
    bucket="my-flow-bucket",
    stored_as_script=True,
    local_script_path="my_flow.py"  # Local file that you want uploaded to the bucket
)
```

The script location can also be provided when registering the flow through the
[`register`](/api/latest/cli/register.html) CLI command through the `--path/-p` option:

```bash
prefect register -p my_flow.py --project MyProject
```
