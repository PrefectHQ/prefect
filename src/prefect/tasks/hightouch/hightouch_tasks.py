import os

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs

from .hightouch_utils import HightouchClient


class HightouchRunSync(Task):
    """
    This task can be used to trigger a new sync run on [Hightouch](https://hightouch.io/).
    Under the hood
    it uses [Hightouch official APIs](https://hightouch.io/docs/syncs/api/#the-hightouch-rest-api).

    Args:
        - api_key (str, optional): The API key to use to authenticate on Hightouch.
        - api_key_env_var (str, optional): The name of the environment variable that contains
            the API key to use to authenticate on Hightouch.
            This value is considered only if `api_key` is not provided.
        - sync_id (int, optional): The ID of the Hightouch sync to run.
        - wait_for_completion (bool, optional): Whether to wait for sync run completion or not.
            Default is `False`.
        - wait_for_completion: (int, optional): Whether to wait for the sync run to finish execution
            or not.
            Default is `False`.
        - wait_time_between_api_calls (int, optional): The number of seconds to
            wait between API calls.
            Default is 10.
        - max_wait_time (int, optional): The maximum number of seconds to wait for the
            Hightouch API to return a response.
            If `wait_for_completion` is `True` and `maximum_wait_time` is not set then the
            task will run until completed or cancelled.
        - **kwargs (optional): Additional keyword arguments to pass to the
            standard Task initalization.
    """

    def __init__(
        self,
        api_key: str = None,
        api_key_env_var: str = None,
        sync_id: int = None,
        wait_for_completion: bool = False,
        wait_time_between_api_calls: int = 10,
        max_wait_time: int = None,
        **kwargs,
    ):
        self.api_key = api_key
        self.api_key_env_var = api_key_env_var
        self.sync_id = sync_id
        self.wait_for_completion = wait_for_completion
        self.wait_time_between_api_calls = wait_time_between_api_calls
        self.max_wait_time = max_wait_time
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "api_key",
        "api_key_env_var",
        "sync_id",
        "wait_for_completion",
        "wait_time_between_api_calls",
        "max_wait_time",
    )
    def run(
        self,
        api_key: str = None,
        api_key_env_var: str = None,
        sync_id: int = None,
        wait_for_completion: bool = False,
        wait_time_between_api_calls: int = 10,
        max_wait_time: int = None,
    ):
        """
        This task can be used to trigger a new sync run on [Hightouch](https://hightouch.io/).
        Under the hood it uses
        [Hightouch official APIs](https://hightouch.io/docs/syncs/api/#the-hightouch-rest-api).

        Args:
            - api_key (str, optional): The API key to use to authenticate on Hightouch.
            - api_key_env_var (str, optional): The name of the environment variable that contains
                the API key to use to authenticate on Hightouch.
                This value is considered only if `api_key` is not provided.
            - sync_id (int, optional): The ID of the Hightouch sync to run.
            - wait_for_completion: (int, optional): Whether to wait for the sync run to finish execution
                or not.
                Default is `False`.
            - wait_time_between_api_calls (int, optional): The number of seconds to
                wait between API calls.
                Default is 10.
            - max_wait_time (int, optional): The maximum number of seconds to wait for the
                If `wait_for_completion` is `True` and `maximum_wait_time` is not set then the
                task will run until completed or cancelled.
                Hightouch API to return a response.

        Raises:
            - `ValueError` if both `api_key` and `api_key_env_var` are missing.
            - `ValueError` if `api_key` is missing and `api_key_env_var` is not found.
            - `ValueError` if `sync_id` is missing.

        Returns:
            - if `wait_for_completion` is `False`, returns the response of
                [Start a new sync run](https://hightouch.io/docs/syncs/api/#start-a-new-sync-run).
            - if `wait_for_completion` is `True`, returns the response of
                [Get sync run status](https://hightouch.io/docs/syncs/api/#get-the-status-of-a-sync-run).
        """
        if not api_key and not api_key_env_var:
            msg = """Neither `api_key` nor `api_key_env_var` have been provided.
            Please provide either an API key or an environment variable
            where the API is stored."""
            raise ValueError(msg)

        if not api_key and api_key_env_var not in os.environ.keys():
            msg = f"""We were unable to find the environment variable ${api_key_env_var}.
            Please make sure the provided environment variable has been
            set with your Hightouch API key."""
            raise ValueError(msg)

        key = api_key if api_key else os.environ[api_key_env_var]

        if not sync_id:
            msg = """`sync_id` has not been provided. Please provide the ID for the
            Hightouch sync that you would like to trigger."""
            raise ValueError(msg)

        wait_api_call_secs = (
            wait_time_between_api_calls if wait_time_between_api_calls > 0 else 10
        )

        ht_client = HightouchClient(api_key=key)
        return ht_client.start_sync_run(
            sync_id=sync_id,
            wait_for_completion=wait_for_completion,
            wait_time_between_api_calls=wait_api_call_secs,
            max_wait_time=max_wait_time,
        )
