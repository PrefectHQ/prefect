# prefect-redis

<p align="center">
    <a href="https://pypi.python.org/pypi/prefect-redis/" alt="PyPI version">
        <img alt="PyPI" src="https://img.shields.io/pypi/v/prefect-redis?color=0052FF&labelColor=090422"></a>
    <a href="https://pepy.tech/badge/prefect-redis/" alt="Downloads">
        <img src="https://img.shields.io/pypi/dm/prefect-redis?color=0052FF&labelColor=090422" /></a>
</p>

For more information about how to use Prefect, please refer to the [Prefect documentation](https://docs.prefect.io/).

## Worker cleanup queue storage

`prefect-redis` provides Redis-backed storage for Prefect server worker cleanup
delivery. To select it, install `prefect-redis` with the server environment and
set:

```bash
PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE=prefect_redis.cleanup_queue
```

Configure the Redis connection with `PREFECT_REDIS_WORKER_CLEANUP_QUEUE_URL` or
the discrete `PREFECT_REDIS_WORKER_CLEANUP_QUEUE_HOST`,
`PREFECT_REDIS_WORKER_CLEANUP_QUEUE_PORT`, and
`PREFECT_REDIS_WORKER_CLEANUP_QUEUE_DB` settings. Use
`PREFECT_REDIS_WORKER_CLEANUP_QUEUE_KEY_PREFIX` to isolate deployments that share
the same Redis database.
