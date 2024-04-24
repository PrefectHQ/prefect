# prefect-gitlab

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-gitlab/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-gitlab?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-gitlab/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-gitlab?color=26272B&labelColor=090422" /></a>
</p>

## Welcome!

`prefect-gitlab` is a Prefect collection for working with GitLab repositories.

## Getting Started

### Python setup

Requires an installation of Python 3.8 or higher.

We recommend using a Python virtual environment manager such as pipenv, conda, or virtualenv.

This integration is designed to work with Prefect 2.3.0 or higher. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Installation

Install `prefect-gitlab` with `pip`:

```bash
pip install prefect-gitlab
```

Then, register the [block types](https://docs.prefect.io/concepts/blocks/)) in this integration to view the storage block type on Prefect Cloud:

```bash
prefect block register -m prefect_gitlab
```

Note, to use the `load` method on a block, you must already have a block document [saved](https://docs.prefect.io/concepts/blocks/).

## Creating a GitLab storage block

### In Python

```python
from prefect_gitlab import GitLabRepository

# public GitLab repository
public_gitlab_block = GitLabRepository(
    name="my-gitlab-block",
    repository="https://gitlab.com/testing/my-repository.git"
)

public_gitlab_block.save()


# specific branch or tag of a GitLab repository
branch_gitlab_block = GitLabRepository(
    name="my-gitlab-block",
    reference="branch-or-tag-name",
    repository="https://gitlab.com/testing/my-repository.git"
)

branch_gitlab_block.save()


# Get all history of a specific branch or tag of a GitLab repository
branch_gitlab_block = GitLabRepository(
    name="my-gitlab-block",
    reference="branch-or-tag-name",
    git_depth=None,
    repository="https://gitlab.com/testing/my-repository.git"
)

branch_gitlab_block.save()

# private GitLab repository
private_gitlab_block = GitLabRepository(
    name="my-private-gitlab-block",
    repository="https://gitlab.com/testing/my-repository.git",
    access_token="YOUR_GITLAB_PERSONAL_ACCESS_TOKEN"
)

private_gitlab_block.save()
```
