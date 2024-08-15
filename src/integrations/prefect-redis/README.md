# prefect-redis

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-redis/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-redis?color=0052FF&labelColor=090422"></a>
    <a href="https://github.com/C4IROcean/prefect-redis/" alt="Stars">
        <img src="https://img.shields.io/github/stars/C4IROcean/prefect-redis?color=0052FF&labelColor=090422" /></a>
    <a href="https://pepy.tech/badge/prefect-redis/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-redis?color=0052FF&labelColor=090422" /></a>
    <a href="https://github.com/C4IROcean/prefect-redis/pulse" alt="Activity">
        <img src="https://img.shields.io/github/commit-activity/m/C4IROcean/prefect-redis?color=0052FF&labelColor=090422" /></a>
    <br>
    <a href="https://prefect-community.slack.com" alt="Slack">
        <img src="https://img.shields.io/badge/slack-join_community-red.svg?color=0052FF&labelColor=090422&logo=slack" /></a>
    <a href="https://discourse.prefect.io/" alt="Discourse">
        <img src="https://img.shields.io/badge/discourse-browse_forum-red.svg?color=0052FF&labelColor=090422&logo=discourse" /></a>
</p>

## Welcome!

Prefect integrations for working with Redis

## Getting Started

### Python setup

Requires an installation of Python 3.7+.

We recommend using a Python virtual environment manager such as pipenv, conda or virtualenv.

These tasks are designed to work with Prefect 2.0. For more information about how to use Prefect, please refer to the [Prefect documentation](https://orion-docs.prefect.io/).

### Installation

Install `prefect-redis` with `pip`:

```bash
pip install prefect-redis
```

Then, register to [view the block](https://orion-docs.prefect.io/ui/blocks/) on Prefect Cloud:

```bash
prefect block register -m prefect_redis.credentials
```

Note, to use the `load` method on Blocks, you must already have a block document [saved through code](https://orion-docs.prefect.io/concepts/blocks/#saving-blocks) or [saved through the UI](https://orion-docs.prefect.io/ui/blocks/).

### Write and run a flow

```python
from prefect import flow
from prefect_redis import (
    RedisCredentials,
    redis_set,
    redis_get,
)


@flow
def example_flow():
    
    # Load credentials-block
    credentials = RedisCredentials.load("my-redis-store")
    
    # Set a redis-key - Supports any object that is not a live connection
    redis_set(credentials, "mykey", {"foo": "bar"})
    
    # Get a redis key
    val = redis_get(credentials, "mykey")
    
    print(val)

example_flow()
```

## Resources

If you encounter any bugs while using `prefect-redis`, feel free to open an issue in the [prefect-redis](https://github.com/C4IROcean/prefect-redis) repository.

If you have any questions or issues while using `prefect-redis`, you can find help in either the [Prefect Discourse forum](https://discourse.prefect.io/) or the [Prefect Slack community](https://prefect.io/slack).

Feel free to ⭐️ or watch [`prefect-redis`](https://github.com/C4IROcean/prefect-redis) for updates too!

## Development

If you'd like to install a version of `prefect-redis` for development, clone the repository and perform an editable install with `pip`:

```bash
git clone https://github.com/C4IROcean/prefect-redis.git

cd prefect-redis/

pip install -e ".[dev]"

# Install linting pre-commit hooks
pre-commit install
```
