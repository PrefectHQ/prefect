"""
This module contains a collection of tasks for interacting with Redis via
the redis-py library.
"""

try:
    from prefect.tasks.redis.redis_tasks import RedisSet, RedisGet, RedisExecute
except ImportError as err:
    raise ImportError(
        'Using `prefect.tasks.redis` requires Prefect to be installed with the "redis" extra.'
    ) from err
