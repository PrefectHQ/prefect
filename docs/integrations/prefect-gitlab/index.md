# prefect-gitlab

The prefect-gitlab library is used to fetch code from a GitLab repository for use in Prefect deployments.

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

### Create GitLab block for code storage

```python
from prefect_gitlab import GitLabRepository

# public GitLab repository
public_gitlab_block = GitLabRepository(
    name="my-gitlab-block",
    repository="https://gitlab.com/testing/my-repository.git"
)


if __name__ == "__main__":
    public_gitlab_block.save()
```

### Specify a branch or tag in the GitLab repository

```python
branch_gitlab_block = GitLabRepository(
    name="my-gitlab-block",
    reference="branch-or-tag-name",
    repository="https://gitlab.com/testing/my-repository.git"
)


if __name__ == "__main__":
    branch_gitlab_block.save()
```

### Specify a private GitLab repository

```python
private_gitlab_block = GitLabRepository(
    name="my-private-gitlab-block",
    repository="https://gitlab.com/testing/my-repository.git",
    access_token="YOUR_GITLAB_PERSONAL_ACCESS_TOKEN"
)

if __name__ == "__main__":
    private_gitlab_block.save()
```
