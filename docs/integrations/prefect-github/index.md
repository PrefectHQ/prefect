# prefect-github

Prefect-github makes it easy to interact with GitHub repositories and credentials.

## Getting started

### Prerequisites

- [Prefect installed](/getting-started/installation/).
- An [GitHub account](https://github.com/).

### Install prefect-github

<div class = "terminal">
```bash
pip install prefect-github
```
</div>

## Examples

Create a deployment where the flow code is stored in a private GitHub repository using the `GitHubRepository` block to access the code.

### Register newly installed block types

Register the block types in the prefect-github module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_github
```
</div>

### Query a GitHub repository and add a star

```python
from prefect import flow
from prefect_github import GitHubCredentials
from prefect_github.repository import query_repository
from prefect_github.mutations import add_star_starrable


@flow()
def github_add_star_flow():
    github_credentials = GitHubCredentials.load("github-token")
    repository_id = query_repository(
        "PrefectHQ",
        "Prefect",
        github_credentials=github_credentials,
        return_fields="id"
    )["id"]
    starrable = add_star_starrable(
        repository_id,
        github_credentials
    )
    return starrable


if __name__ == "__main__":
    github_add_star_flow()
```

## Resources

For assistance using GitHub, consult the [GitHub documentation]().

Refer to the prefect-github API documentation linked in the sidebar to explore all the capabilities of the prefect-github library.
