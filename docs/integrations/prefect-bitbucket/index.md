# prefect-bitbucket

Prefect-bitbucket is a Prefect integration that allows you to interact with Bitbucket repositories and credentials. TK worker need installed for?

## Getting Started

### Prerequisites

- [Prefect installed](/getting-started/installation/).
- A [Bitbucket account](https://bitbucket.org/product).

### Install prefect-bitbucket

<div class = "terminal">
```bash
pip install prefect-bitbucket
```
</div>

### Register newly installed block types

Register the block types in the prefect-aws module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_bitbucket
```
</div>

## Examples

In the examples below, you create blocks with Python code.
Alternatively, each block can be created through the Prefect UI.

### Load a pre-existing BitBucketCredentials block

```python
from prefect import flow
from prefect_bitbucket.credentials import BitBucketCredentials

@flow
def use_stored_bitbucket_creds_flow():
    bitbucket_credentials_block = BitBucketCredentials.load("BLOCK_NAME")

    return bitbucket_credentials_block

use_stored_bitbucket_creds_flow()
```

### Create a new BitBucketCredentials block

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
