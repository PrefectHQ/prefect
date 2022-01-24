import os
from requests import Session
from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine.signals import FAIL
import json
import jwt
import time
from typing import Dict, List, Union


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
            - The Cube.js JSON response.

        """

        if not subdomain and not url:
            raise ValueError("Missing both `subdomain` and `url`.")

        if not api_secret and api_secret_env_var not in os.environ:
            raise ValueError("Missing `api_secret` and `api_secret_env_var` not found.")

        if not query:
            raise ValueError("Missing `query`.")

        cube_base_url = self.__CUBEJS_CLOUD_BASE_URL
        if subdomain:
            cube_base_url = f"{cube_base_url.format(subdomain=subdomain)}/cubejs-api"
        else:
            cube_base_url = url
        query_api_url = f"{cube_base_url}/v1/load"

        self.logger.debug(f"Query URL: {query_api_url}")

        secret = api_secret if api_secret else os.environ[api_secret_env_var]

        if security_context:

            extended_context = security_context
            if "exp" not in security_context and "expiresIn" not in security_context:
                extended_context["expiresIn"] = "7d"
            api_token = jwt.encode(
                payload=extended_context, key=secret, algorithm="HS256"
            )

            self.logger.debug("JWT token generated with security context.")

        else:
            api_token = jwt.encode(payload={}, key=secret)

        session = Session()
        session.headers = {
            "Content-type": "application/json",
            "Authorization": api_token,
        }

        params = {"query": json.dumps(query)}

        wait_api_call_secs = (
            wait_time_between_api_calls if wait_time_between_api_calls > 0 else 10
        )
        elapsed_wait_time = 0
        while not max_wait_time or elapsed_wait_time <= max_wait_time:

            with session.get(url=query_api_url, params=params) as response:
                self.logger.debug(f"URL is: {response.url}")

                if response.status_code == 200:
                    data = response.json()

                    if "error" in data.keys() and "Continue wait" in data["error"]:
                        msg = (
                            "Cube.js load API still running."
                            "Waiting {wait_api_call_secs} seconds before retrying"
                        )
                        self.logger.info(msg)
                        time.sleep(wait_api_call_secs)
                        elapsed_wait_time += wait_api_call_secs
                        continue

                    else:
                        return data

                else:
                    raise FAIL(
                        message=f"Cube.js load API failed! Error is: {response.reason}"
                    )

        raise FAIL(
            message=f"Cube.js load API took longer than {max_wait_time} seconds to provide a response."
        )
