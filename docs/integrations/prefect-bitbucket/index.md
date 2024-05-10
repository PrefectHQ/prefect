# prefect-bitbucket

The prefect-bitbucket library makes it easy to interact with Bitbucket repositories and credentials.

## Getting Started

### Prerequisites

- [Prefect installed](/getting-started/installation/).
- A [Bitbucket account](https://bitbucket.org/product).

### Install prefect-bitbucket

<div class = "terminal">
```bash
pip install -U prefect-bitbucket
```
</div>

### Register newly installed block types

Register the block types in the prefect-bitbucket module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_bitbucket
```
</div>

## Examples

In the examples below, you create blocks with Python code.
Alternatively, blocks can be created through the Prefect UI.

## Store deployment flow code in a private Bitbucket repository

To create a deployment and run a deployment where the flow code is stored in a private Bitbucket repository, you can use the `BitbucketCredentials` block.

A deployment can use flow code stored in a Bitbucket repository without using this library in either of the following cases:

- The repository is public
- The deployment uses a [Secret block](https://docs.prefect.io/latest/concepts/blocks/) to store the token

Code to create a Bitbucket Credentials block:

```python
from prefect_bitbucket import BitbucketCredentials

bitbucket_credentials_block = BitbucketCredentials(url="https://bitbucket.com/my_org/my_private-repo.git", token="my_token")

bitbucket_credentials_block.save(name="my-bitbucket-credentials-block")
```

!!! info "Differences between Bitbucket Server and Bitbucket Cloud"

    For Bitbucket Cloud, only set the `token` to authenticate. For Bitbucket Server, set both the `token` and the `username`.

### Access flow code stored in a private Bitbucket repository in a deployment

Use the credentials block you created above to pass the Bitbucket access token during deployment creation. The code below assumes there's flow code stored in a private Bitbucket repository.

```python
from prefect import flow
from prefect.runner.storage import GitRepository
from prefect_bitbucket import BitbucketCredentials


if __name__ == "__main__":
    flow.from_source(
        source=GitRepository(
        url="https://bitbucket.com/org/private-repo.git",
        credentials=BitbucketCredentials.load("my-bitbucket-credentials-block")
    ),
    entrypoint="my_file.py:my_flow",
    ).deploy(
        name="private-bitbucket-deploy",
        work_pool_name="my_pool",
        build=False
    )
```

Alternatively, if you use a `prefect.yaml` file to create the deployment, reference the Bitbucket Credentials block in the `pull` step:

```yaml
pull:
    - prefect.deployments.steps.git_clone:
        repository: https://github.com/org/repo.git
        access_token: "{{ prefect.blocks.bitbucket-credentials.my-credentials }}"
```

### Interact with a Bitbucket repository

The code below shows how to reference a particular branch or tag of a Bitbucket repository.

```python
from prefect_bitbucket import BitbucketRepository

def save_private_bitbucket_block():
    private_bitbucket_block = BitbucketRepository(
        repository="https://bitbucket.com/testing/my-repository.git",
        access_token="YOUR_GITLAB_PERSONAL_ACCESS_TOKEN",
        reference="branch-or-tag-name",
    )

    private_bitbucket_block.save("my-private-bitbucket-block")


if __name__ == "__main__":
    save_private_bitbucket_block()
```

Exclude the `access_token` field if the repository is public and exclude the `reference` field to use the default branch.

Use the newly created block to interact with the Bitbucket repository.

For example, download the repository contents with the `.get_directory()` method like this:

```python
from prefect_bitbucket.repositories import BitbucketRepository

def fetch_repo():
    private_bitbucket_block = BitbucketRepository.load("my-bitbucket-block")
    repo = private_bitbucket_block.get_directory()
    return repo

if __name__ == "__main__":
    fetch_repo()
```

## Resources

For assistance using Bitbucket, consult the [Bitbucket documentation](https://bitbucket.com).

Refer to the prefect-bitbucket API documentation linked in the sidebar to explore all the capabilities of the prefect-bitbucket library.
