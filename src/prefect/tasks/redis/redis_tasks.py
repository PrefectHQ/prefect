from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

import redis


class RedisSet(Task):
    """
    Task for setting a Redis key-value pair.

    Args:
        - connection (Redis Connection , optional): if not provided, connection will be established using
            host, port, db, and password parameters
        - host (str, optional): name of Redis host, defaults to 'localhost'
        - port (int, optional): Redis port, defaults to 6379
        - db (int, optional): redis database index, defaults to 0
        - password (str, optional): Redis password, defaults to None
        - redis_key (optional): Redis key to be set, can be provided at initialization or runtime
        - redis_val (optional): Redis val to be set, can be provided at initialization or runtime
        - ex (int, optional): if provided, sets an expire flag, in seconds, on 'redis_key' set
        - px (int, optional): if provided, sets an expire flag, in milliseconds, on 'redis_key' set
        - nx (int, optional): if set to True, set the value at 'redis_key' to 'redis_val' only
            if it does not exist, defaults to False
        - xx (int, optional): if set to True, set the value at 'redis_key' to 'redis_val' only
            if it already exists, defaults to False
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        connection=None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = None,
        redis_key=None,
        redis_val=None,
        ex: int = None,
        px: int = None,
        nx: bool = False,
        xx: bool = False,
        **kwargs
    ):
        ## connect to Redis
        if connection:
            self.connection = connection
        else:
            self.connection = redis.Redis(
                host=host, port=port, db=db, password=password
            )

        self.redis_key = redis_key
        self.redis_val = redis_val
        self.ex = ex
        self.px = px
        self.nx = nx
        self.xx = xx
        super().__init__(**kwargs)

    @defaults_from_attrs("redis_key", "redis_val", "ex", "px", "nx", "xx")
    def run(
        self,
        redis_key=None,
        redis_val=None,
        ex: int = None,
        px: int = None,
        nx: bool = False,
        xx: bool = False,
    ):
        """
        Task run method. Sets Redis key-value pair.

        Args:
            - redis_key (optional): Redis key to be set, can be provided at initialization or runtime
            - redis_val (optional): Redis val to be set, can be provided at initialization or runtime
            - ex (int, optional): if provided, sets an expire flag, in seconds, on 'redis_key' set
            - px (int, optional): if provided, sets an expire flag, in milliseconds, on 'redis_key' set
            - nx (int, optional): if set to True, set the value at 'redis_key' to 'redis_val' only
                if it does not exist, defaults to False
            - xx (int, optional): if set to True, set the value at 'redis_key' to 'redis_val' only
                if it already exists, defaults to False

        Returns:
            - bool: status of set operation

        Raises:
            - ValueError: if redis_key or redis_val is not provided
        """
        if None in (redis_key, redis_val):
            raise ValueError("redis_key and redis_val must be provided")

        result = self.connection.set(
            name=redis_key, value=redis_val, ex=ex, px=px, nx=nx, xx=xx
        )

        return result


class RedisGet(Task):
    """
    Task for getting a value based on key from a Redis connection.

    Args:
        - connection (Redis Connection , optional): if not provided, connection will be established using
            host, port, db, and password parameters
        - host (str, optional): name of Redis host, defaults to 'localhost'
        - port (int, optional): Redis port, defaults to 6379
        - db (int, optional): redis database index, defaults to 0
        - password (str, optional): Redis password, defaults to None
        - redis_key (optional): Redis key to get value, can be provided at initialization or runtime
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        connection=None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = None,
        redis_key=None,
        **kwargs
    ):
        ## connect to Redis
        if connection:
            self.connection = connection
        else:
            self.connection = redis.Redis(
                host=host, port=port, db=db, password=password
            )

        self.redis_key = redis_key
        super().__init__(**kwargs)

    @defaults_from_attrs("redis_key")
    def run(self, redis_key=None):
        """
        Task run method.

        Args:
            - redis_key (optional): Redis key to get value, can be provided at initialization or runtime

        Returns:
            - value: value associated with redis_key

        Raises:
            - ValueError: if redis_key is not provided
        """
        if not redis_key:
            raise ValueError("redis_key must be provided")

        result = self.connection.get(name=redis_key)

        return result


class RedisExecute(Task):
    """
    Task for executing a command against a Redis connection

    Args:
        - connection (Redis Connection , optional): if not provided, connection will be established using
            host, port, db, and password parameters
        - host (str, optional): name of Redis host, defaults to 'localhost'
        - port (int, optional): Redis port, defaults to 6379
        - db (int, optional): redis database index, defaults to 0
        - password (str, optional): Redis password, defaults to None
        - redis_cmd (str, optional): Redis command to execute, must be provided at initialization or
            runtime
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        connection=None,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = None,
        redis_cmd: str = None,
        **kwargs
    ):
        ## connect to Redis
        if connection:
            self.connection = connection
        else:
            self.connection = redis.Redis(
                host=host, port=port, db=db, password=password
            )

        self.redis_cmd = redis_cmd
        super().__init__(**kwargs)

    @defaults_from_attrs("redis_cmd")
    def run(self, redis_cmd: str = None):
        """
        Task run method. Executes a command against a Redis connection.

        Args:
            - redis_cmd (str, optional): Redis command to execute, must be provided at initialization or
                runtime

        Returns:
            - result: result of executed Redis command
        """
        if not redis_cmd:
            raise ValueError("A redis command must be specified")

        result = self.connection.execute_command(redis_cmd)

        return result
