# prefect-bitbucket

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-bitbucket/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-bitbucket?color=0052FF&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-bitbucket/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-bitbucket?color=0052FF&labelColor=090422" /></a>
</p>


## Welcome!

Prefect integrations for working with Bitbucket repositories.

## Getting Started

### Python setup

Requires an installation of Python 3.8+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2.0. For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

### Installation

Install `prefect-bitbucket` with `pip`:

```bash
pip install prefect-bitbucket
```

Then, register to [view the block](https://docs.prefect.io/ui/blocks/) on Prefect Cloud:

```bash
prefect block register -m prefect_bitbucket
```

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://docs.prefect.io/concepts/blocks/#saving-blocks) or [saved through the UI](https://docs.prefect.io/ui/blocks/).

### Write and run a flow
#### Load a pre-existing BitBucketCredentials block

```python
from prefect import flow
from prefect_bitbucket.credentials import BitBucketCredentials

@flow
def use_stored_bitbucket_creds_flow():
    bitbucket_credentials_block = BitBucketCredentials.load("BLOCK_NAME")

    return bitbucket_credentials_block

use_stored_bitbucket_creds_flow()
```

#### Create a new BitBucketCredentials block in a flow

```python
from prefect import flow
from prefect_bitbucket.credentials import BitBucketCredentials

@flow
def create_new_bitbucket_creds_flow():
    bitbucket_credentials_block = BitBucketCredentials(
        token="my-token",
        username="my-username"
    )

create_new_bitbucket_creds_flow()
```

#### Create a BitBucketRepository block for a public repo
```python
from prefect_bitbucket import BitBucketRepository

public_repo = "https://bitbucket.org/my-workspace/my-repository.git"

# Creates a public BitBucket repository BitBucketRepository block
public_bitbucket_block = BitBucketRepository(
    repository=public_repo
)

# Saves the BitBucketRepository block to your Prefect workspace (in the Blocks tab)
public_bitbucket_block.save("my-bitbucket-block")
```

#### Create a BitBucketRepository block for a public repo at a specific branch or tag
```python
from prefect_bitbucket import BitBucketRepository

public_repo = "https://bitbucket.org/my-workspace/my-repository.git"

# Creates a public BitBucket repository BitBucketRepository block
branch_bitbucket_block = BitBucketRepository(
    reference="my-branch-or-tag",  # e.g "master"
    repository=public_repo
)

# Saves the BitBucketRepository block to your Prefect workspace (in the Blocks tab)
branch_bitbucket_block.save("my-bitbucket-branch-block")
```
#### Create a new BitBucketCredentials block and a BitBucketRepository block for a private repo
```python
from prefect_bitbucket import BitBucketCredentials, BitBucketRepository

# For a private repo, we need credentials to access it
bitbucket_credentials_block = BitBucketCredentials(
    token="my-token",
    username="my-username"  # optional
)

# Saves the BitBucketCredentials block to your Prefect workspace (in the Blocks tab)
bitbucket_credentials_block.save(name="my-bitbucket-credentials-block")


# Creates a private BitBucket repository BitBucketRepository block
private_repo = "https://bitbucket.org/my-workspace/my-repository.git"
private_bitbucket_block = BitBucketRepository(
    repository=private_repo,
    bitbucket_credentials=bitbucket_credentials_block
)

# Saves the BitBucketRepository block to your Prefect workspace (in the Blocks tab)
private_bitbucket_block.save(name="my-private-bitbucket-block")
```

#### Use a preexisting BitBucketCredentials block to create a BitBucketRepository block for a private repo
```python
from prefect_bitbucket import BitBucketCredentials, BitBucketRepository

# Loads a preexisting BitBucketCredentials block
BitBucketCredentials.load("my-bitbucket-credentials-block")

# Creates a private BitBucket repository BitBucketRepository block
private_repo = "https://bitbucket.org/my-workspace/my-repository.git"
private_bitbucket_block = BitBucketRepository(
    repository=private_repo,
    bitbucket_credentials=bitbucket_credentials_block
)

# Saves the BitBucketRepository block to your Prefect workspace (in the Blocks tab)
private_bitbucket_block.save(name="my-private-bitbucket-block")
```

!!! info "Differences between Bitbucket Server and Bitbucket Cloud"

    For Bitbucket Cloud, only set the `token` to authenticate. For Bitbucket Server, set both the `token` and the `username`.