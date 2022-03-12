import os
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
import json
from typing import Dict, List, Union

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
