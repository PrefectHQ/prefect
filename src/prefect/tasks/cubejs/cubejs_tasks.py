import os
import time
import prefect
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
import json
from typing import Dict, List, Union
from prefect.engine.signals import LOOP, FAIL

from .cubejs_utils import CubeJSClient


class CubeJSQueryTask(Task):

    """
    This task calls Cueb.js load API and returns the result
    as a JSON object.
    More info about Cube.js load API at
    https://cube.dev/docs/rest-api#api-reference-v-1-load.

    Args:
        - subdomain (str, optional): The subdomain to use to get the data.
            If provided, `subdomain` takes precedence over `url`.
            This is likely to be useful to Cube Cloud users.
        - url (str, optional): The URL to use to get the data.
            This is likely to be useful to users of self-hosted Cube.js.
        - api_secret (str, optional): The API secret used to generate an
            API token for authentication.
            If provided, it takes precedence over `api_secret_env_var`.
        - api_secret_env_var (str, optional): The name of the env var that contains
            the API secret to use to generate an API token for authentication.
            Defaults to `CUBEJS_API_SECRET`.
        - query (dict, list, optional): `dict` or `list` representing
            valid Cube.js queries.
            If you pass multiple queries, then be aware of Cube.js Data Blending.
            More info at https://cube.dev/docs/rest-api#api-reference-v-1-load
            and at https://cube.dev/docs/schema/advanced/data-blending.
            Query format can be found at: https://cube.dev/docs/query-format.
        - include_generated_sql: (bool, optional): Whether the return object should
            include SQL info or not.
            Default to `False`.
        - security_context (str, dict, optional): The security context to use
            during authentication.
            If the security context does not contain an expiration period,
            then a 7-day expiration period is added automatically.
            More info at: https://cube.dev/docs/security/context.
        - wait_time_between_api_calls (int, optional): The number of seconds to
            wait between API calls.
            Default to 10.
        - max_wait_time (int, optional): The number of seconds to wait for the
            Cube.js load API to return a response.
        - **kwargs (optional): Additional keyword arguments to pass to the
            standard Task initalization.

    """

    __CUBEJS_CLOUD_BASE_URL = "https://{subdomain}.cubecloud.dev"

    def __init__(
        self,
        subdomain: str = None,
        url: str = None,
        api_secret: str = None,
        api_secret_env_var: str = "CUBEJS_API_SECRET",
        query: Union[Dict, List[Dict]] = None,
        include_generated_sql: bool = False,
        security_context: Union[str, Dict] = None,
        wait_time_between_api_calls: int = 10,
        max_wait_time: int = None,
        **kwargs,
    ):
        self.subdomain = subdomain
        self.url = url
        self.api_secret = api_secret
        self.api_secret_env_var = api_secret_env_var
        self.query = query
        self.include_generated_sql = include_generated_sql
        self.security_context = security_context
        self.wait_time_between_api_calls = wait_time_between_api_calls
        self.max_wait_time = max_wait_time
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "subdomain",
        "url",
        "api_secret",
        "api_secret_env_var",
        "query",
        "include_generated_sql",
        "security_context",
        "wait_time_between_api_calls",
        "max_wait_time",
    )
    def run(
        self,
        subdomain: str = None,
        url: str = None,
        api_secret: str = None,
        api_secret_env_var: str = "CUBEJS_API_SECRET",
        query: Union[Dict, List[Dict]] = None,
        include_generated_sql: bool = False,
        security_context: Union[str, Dict] = None,
        wait_time_between_api_calls: int = 10,
        max_wait_time: int = None,
    ):
        """
        Task run method to perform a query using Cube.js load API.

        Args:
            - subdomain (str, optional): The subdomain to use to get the data.
                If provided, `subdomain` takes precedence over `url`.
                This is likely to be useful to Cube Cloud users.
            - url (str, optional): The URL to use to get the data.
                This is likely the preferred method for self-hosted Cube
                deployments.
                For Cube Cloud deployments, the URL should be in the form
                `https://<cubejs-generated-host>/cubejs-api`.
            - api_secret (str, optional): The API secret used to generate an
                API token for authentication.
                If provided, it takes precedence over `api_secret_env_var`.
            - api_secret_env_var (str, optional): The name of the env var that contains
                the API secret to use to generate an API token for authentication.
                Defaults to `CUBEJS_API_SECRET`.
            - query (dict, list, optional): `dict` or `list` representing
                valid Cube.js queries.
                If you pass multiple queries, then be aware of Cube.js Data Blending.
                More info at https://cube.dev/docs/rest-api#api-reference-v-1-load
                and at https://cube.dev/docs/schema/advanced/data-blending.
                Query format can be found at: https://cube.dev/docs/query-format.
            - include_generated_sql: (bool, optional): Whether the return object should
                include SQL info or not.
                Default to `False`.
            - security_context (str, dict, optional): The security context to use
                during authentication.
                If the security context does not contain an expiration period,
                then a 7-day expiration period is added automatically.
                More info at https://cube.dev/docs/security/context.
            - wait_time_between_api_calls (int, optional): The number of seconds to
                wait between API calls.
                Default to 10.
            - max_wait_time (int, optional): The number of seconds to wait for the
                Cube.js load API to return a response.

        Raises:
            - ValueError if both `subdomain` and `url` are missing.
            - ValueError if `api_token` is missing and `api_token_env_var` cannot be found.
            - ValueError if `query` is missing.
            - `prefect.engine.signals.FAIL` if the Cube.js load API fails.
            - `prefect.engine.signals.FAIL` if the Cube.js load API takes more than
                `max_wait_time` seconds to respond.

        Returns:
            - The Cube.js JSON response, augmented with SQL
                information if `include_generated_sql` is `True`.

        """

        if not subdomain and not url:
            raise ValueError("Missing both `subdomain` and `url`.")

        if not api_secret and api_secret_env_var not in os.environ:
            raise ValueError("Missing `api_secret` and `api_secret_env_var` not found.")

        if not query:
            raise ValueError("Missing `query`.")

        secret = api_secret if api_secret else os.environ[api_secret_env_var]

        wait_api_call_secs = (
            wait_time_between_api_calls if wait_time_between_api_calls > 0 else 10
        )

        cubejs_client = CubeJSClient(
            subdomain=subdomain,
            url=url,
            security_context=security_context,
            secret=secret,
            wait_api_call_secs=wait_api_call_secs,
            max_wait_time=max_wait_time,
        )

        params = {"query": json.dumps(query)}

        # Retrieve data from Cube.js
        data = cubejs_client.get_data(
            params=params, include_generated_sql=include_generated_sql
        )

        return data


class CubePreAggregationsBuildTask(Task):
    """
    This task uses Cube `pre-aggregations/jobs` API to build pre-aggregations
    specified by the pre-aggregations selector.

    Args:
        - subdomain (str, optional): The subdomain to use to get the data.
            If provided, `subdomain` takes precedence over `url`.
            This is likely to be useful to Cube Cloud users.
        - url (str, optional): The URL to use to get the data.
            This is likely to be useful to users of self-hosted Cube.
        - api_secret (str, optional): The API secret used to generate an
            API token for authentication.
            If provided, it takes precedence over `api_secret_env_var`.
        - api_secret_env_var (str, optional): The name of the env var that contains
            the API secret to use to generate an API token for authentication.
            Defaults to `CUBEJS_API_SECRET`.
        - security_context (str, dict, optional): The security context to use
            during authentication.
            If the security context does not contain an expiration period,
            then a 7-day expiration period is added automatically.
            More info at: https://cube.dev/docs/security/context.
        - selector (dict): `dict` representing valid Cube `pre-aggregations/jobs`
            API selector object.
        - wait_for_job_run_completion (boolean, optional):
            Whether the task should wait for the job run completion or not.
            Default to False.
        - wait_time_between_api_calls (int, optional): The number of seconds to
            wait between API calls.
            Default to 10.
        - **kwargs (optional): Additional keyword arguments to pass to the
            standard Task initalization.
    """

    def __init__(
        self,
        subdomain: str = None,
        url: str = None,
        api_secret: str = None,
        api_secret_env_var: str = "CUBEJS_API_SECRET",
        security_context: Union[str, Dict] = None,
        selector: Dict = None,
        wait_for_job_run_completion: bool = False,
        wait_time_between_api_calls: int = 10,
        **kwargs,
    ):
        if not subdomain and not url:
            raise ValueError("Missing both `subdomain` and `url`.")

        if not api_secret and api_secret_env_var not in os.environ:
            raise ValueError("Missing `api_secret` and `api_secret_env_var` not found.")

        self.subdomain = subdomain
        self.url = url
        self.api_secret = api_secret
        self.api_secret_env_var = api_secret_env_var
        self.selector = selector
        self.security_context = security_context
        self.secret = api_secret if api_secret else os.environ[api_secret_env_var]
        self.wait_for_job_run_completion = wait_for_job_run_completion
        self.wait_time_between_api_calls = wait_time_between_api_calls
        self.cubejs_client = CubeJSClient(
            subdomain=subdomain,
            url=url,
            security_context=security_context,
            secret=self.secret,
            max_wait_time=None,
            wait_api_call_secs=None,
        )
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "subdomain",
        "url",
        "api_secret",
        "api_secret_env_var",
        "security_context",
        "selector",
        "wait_for_job_run_completion",
        "wait_time_between_api_calls",
    )
    def run(
        self,
        subdomain: str = None,
        url: str = None,
        api_secret: str = None,
        api_secret_env_var: str = "CUBEJS_API_SECRET",
        security_context: Union[str, Dict] = None,
        selector: Dict = None,
        wait_for_job_run_completion: bool = False,
        wait_time_between_api_calls: int = 10,
    ):
        """
        Task run method to perform pre-aggregations build.

        Args:
            - subdomain (str, optional): The subdomain to use to get the data.
                If provided, `subdomain` takes precedence over `url`.
                This is likely to be useful to Cube Cloud users.
            - url (str, optional): The URL to use to get the data.
                This is likely the preferred method for self-hosted Cube
                deployments.
                For Cube Cloud deployments, the URL should be in the form
                `https://<cubejs-generated-host>/cubejs-api`.
            - api_secret (str, optional): The API secret used to generate an
                API token for authentication.
                If provided, it takes precedence over `api_secret_env_var`.
            - api_secret_env_var (str, optional): The name of the env var that contains
                the API secret to use to generate an API token for authentication.
                Defaults to `CUBEJS_API_SECRET`.
            - security_context (str, dict, optional): The security context to use
                during authentication.
                If the security context does not contain an expiration period,
                then a 7-day expiration period is added automatically.
                More info at https://cube.dev/docs/security/context.
            - selector (dict): `dict` representing valid Cube `pre-aggregations/jobs`
                API `selector` object.
            - wait_for_job_run_completion (boolean, optional):
                Whether the task should wait for the job run completion or not.
                Default to False.
            - wait_time_between_api_calls (int, optional): The number of seconds to
                wait between API calls.
                Default to 10.

        Raises:
            - ValueError if both `subdomain` and `url` are missing.
            - ValueError if `api_token` is missing and `api_token_env_var` cannot be found.
            - ValueError if `selector` is missing.
            - `prefect.engine.signals.FAIL` if the Cube `pre-aggregations/jobs` API fails.
            - `prefect.engine.signals.FAIL` if any pre-aggregations were not built.

        Returns:
            - If `wait_for_job_run_completion = False`, then returns the Cube
                `pre-aggregations/jobs` API trigger run result.
            - If `wait_for_job_run_completion = True`, then returns `True`
                if pre-aggregations were successfully built. Raise otherwise.
        """

        if not selector:
            raise ValueError("Missing `selector`.")

        count = prefect.context.get("task_loop_count", 1)
        tokens = prefect.context.get("task_loop_result", [])

        if count == 1:
            tokens = self._post_pre_aggregations_jobs(selector=selector)
            if not wait_for_job_run_completion:
                return tokens

        statuses = self._get_pre_aggregations_jobs_statuses(tokens=tokens)
        tokens = self._in_process(statuses=statuses)

        if len(tokens) == 0:
            return True

        raise LOOP(message=f'{"looping..."}', result=tokens)

    def _post_pre_aggregations_jobs(self, selector: Dict = None):
        """
        Initializes the build process by using the appropriate API call.
        """

        query = json.dumps(
            {
                "action": "post",
                "selector": selector,
            }
        )

        tokens = self.cubejs_client.pre_aggregations_jobs(query=query)
        return tokens

    def _get_pre_aggregations_jobs_statuses(
        self,
        tokens: List[str] = None,
    ):
        """
        Gets posted job's statuses by using the appropriate API call.
        """

        query = json.dumps(
            {
                "action": "get",
                "resType": "object",
                "tokens": tokens,
            }
        )

        statuses = self.cubejs_client.pre_aggregations_jobs(query=query)
        return statuses

    def _in_process(self, statuses: Dict = None):
        """
        Returns the pre-aggregations jobs token that still in progress.

        Raises:
            - `prefect.engine.signals.FAIL` if the Cube `pre-aggregations/jobs` API returns
                status with the errors or one or more partitions are missed.
        """

        missing_only = True
        tokens = statuses.keys()
        in_process = []

        for token in tokens:
            status = statuses[token]["status"]
            if status.find("failure") >= 0:
                raise FAIL(message=f"Cube pre-aggregations build failed: {status}.")
            if status != "missing_partition":
                missing_only = False
            if status != "done":
                in_process.append(token)

        if missing_only:
            raise FAIL(
                message=f'{"Cube pre-aggregations build failed: missing partitions."}'
            )

        time.sleep(self.wait_time_between_api_calls)
        return in_process
