# prefect-gitlab

The prefect-gitlab makes it easy to interact with GitLab repositories and credentials.

## Getting Started

### Prerequisites

- [Prefect installed](/getting-started/installation/).
- A [GitLab account](https://gitlab.com/).

### Install prefect-gitlab

<div class = "terminal">
```bash
pip install -U prefect-gitlab
```
</div>

Register the block types in the prefect-gitlab module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_gitlab
```
</div>

## Examples

## Store deployment flow code in a private GitLab repository

To create a deployment and run a deployment where the flow code is stored in a private GitLab repository, you can use the `GitLabCredentials` block.

A deployment can use flow code in a GitLab repository without this library in the following cases:

- The repository is public
- The compute environment is authenticated to the private repository
- The deployment uses a Secret block to store the required credentials

### Access private flow code stored in a GitLab repository in a Deployment

Use the UI or code to create a GitLab Credentials block.
Then reference the block in the deployment creation code:

```python
from prefect import flow

flow.from_source().deploy(name="my-deploy")

```

If using a `prefect.yaml` file to create the deployment, reference the GitLab Credentials block in the `pull` step:

```yaml
pull:
    - prefect.deployments.steps.git_clone:
        repository: https://github.com/org/repo.git
        access_token: "{{ prefect.blocks.gitlab-credentials.my-credentials }}"
```

### Interact with a GitLab repository

Create a GitLab Repository block in the UI or in code.
The code below shows how to reference a particular branch or tag of a private GitLab repository.

```python
from prefect_gitlab.repositories import GitLabRepository

def save_private_gitlab_block():
    private_gitlab_block = GitLabRepository(
        repository="https://gitlab.com/testing/my-repository.git",
        access_token="YOUR_GITLAB_PERSONAL_ACCESS_TOKEN",
        reference="branch-or-tag-name",
    )

    private_gitlab_block.save("my-private-gitlab-block")


if __name__ == "__main__":
    save_private_gitlab_block()
```

Leave the `access_token` field empty if the repository is public.
Leave the `reference` field empty to use the default branch.

Use the newly created block to interact with the GitLab repository.

For example, download the repository contents with the `.get_directory()` method.

```python
from prefect_gitlab.repositories import GitLabRepository

def fetch_repo():
    private_gitlab_block = GitLabRepository.load("my-private-gitlab-block")
    repo = private_gitlab_block.get_directory()
    return repo

if __name__ == "__main__":
    fetch_repo()
```

## Resources

For assistance using GitLab, consult the [GitLab documentation](https://gitlab.com).

Refer to the prefect-gitlab API documentation linked in the sidebar to explore all the capabilities of the prefect-gitlab library.
