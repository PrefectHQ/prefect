# `prefect-redis`

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-redis/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-redis?color=26272B&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-redis/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-redis?color=26272B&labelColor=090422" /></a>
</p>

The prefect-redis library makes it easy to interact with redis.

## Getting Started

### Prerequisites

- [Prefect installed](/3.0rc/getting-started/installation/).
- [Redis](https://redis.io/docs/latest/get-started/)

### Install prefect-redis

<div class = "terminal">
```bash
pip install -U prefect-redis
```
</div>

### Register newly installed block types

Register the block types in the prefect-redis module to make them available for use.

<div class = "terminal">
```bash
prefect block register -m prefect_redis
```
</div>

## Examples

In the examples below, you create blocks with Python code.
Alternatively, blocks can be created through the Prefect UI.

### Read and write files to Redis

Store file content in a redis block and retrieve it later.

```python
from pathlib import Path
from prefect import flow
from prefect_redis import RedisStorageContainer


@flow
def redis_flow():
    file_path = Path("test-example.txt")
    file_content = b"Hello, Prefect!"

    container = RedisStorageContainer.from_host(host="localhost", port=6379, db=0)

    # Write the file to the container
    container.write_path(file_path, file_content)

    # Read the file from the container and check the contents
    retrieved = container.read_path(file_path)
    assert retrieved == file_content

    return retrieved


if __name__ == "__main__":
    redis_flow()
```

## Resources

For assistance using redis, consult the [redis documentation](https://redis.io/docs/latest/).

Refer to the prefect-redis API documentation linked in the sidebar to explore all the capabilities of the prefect-redis library.


The `prefect-dask` collection makes it easy to include distributed processing for your flows. Check out the examples below to get started!