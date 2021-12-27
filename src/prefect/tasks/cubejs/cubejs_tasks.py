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
    This task calls CuebJS Quuery API and returns the result
    as a JSON object.
    More info about CubeJS Query API at
    https://cube.dev/docs/rest-api#api-reference-v-1-load

    Args:
        - subdomain (str, optional): The subdomain to use to get the data.
            If provided, `subdomain` takes precedence over `url`.
            This is likely to be useful to Cube Cloud users.
        - url (str, optional): The URL to use to get the data.
            This is likely to be useful to users of self-hosted Cube.
        - api_secret (str, optional): The API secretto use to generate an
            API token to use to authenticate.
            If provided, it takes precedence over `api_secret_env_var`.
        - api_secret_env_var (str, optional): The name of the env var that contains
            the API secret to use to generate an API token to use to authenticate.
            Defaults to `CUBEJS_API_SECRET`.
        - query (dict, list, optional): `dict` or `list` representing
            valid CubeJS queries.
            If you pass multiple queries, then be aware of CubeJS Data Blending.
            More info at: https://cube.dev/docs/rest-api#api-reference-v-1-load
            and at: https://cube.dev/docs/schema/advanced/data-blending
        - security_context (str, dict, optional): The security context to use
            during authentication.
            If the security context does not contain an expiration period,
            then a 7 days expiration period is added automatically.
            More info at: https://cube.dev/docs/security/context
        - **kwargs (optional): additional keyword arguments to pass to the
            standard Task initalization

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
        **kwargs,
    ):
        self.subdomain = subdomain
        self.url = url
        self.api_secret = api_secret
        self.api_secret_env_var = api_secret_env_var
        self.query = query
        self.security_context = security_context
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "subdomain",
        "url",
        "api_secret",
        "api_secret_env_var",
        "query",
        "security_context",
    )
    def run(
        self,
        subdomain: str = None,
        url: str = None,
        api_secret: str = None,
        api_secret_env_var: str = "CUBEJS_API_SECRET",
        query: Union[Dict, List[Dict]] = None,
        security_context: Union[str, Dict] = None,
    ):
        """
        Task run method to perform a query using CubeJS Query API.

        Args:
            - subdomain (str, optional): The subdomain to use to get the data.
                If provided, `subdomain` takes precedence over `url`.
                This is likely to be useful to Cube Cloud users.
            - url (str, optional): The URL to use to get the data.
                This is likely to be useful to users of self-hosted Cube.
            - api_secret (str, optional): The API secretto use to generate an
                API token to use to authenticate.
                If provided, it takes precedence over `api_secret_env_var`.
            - api_secret_env_var (str, optional): The name of the env var that contains
                the API secret to use to generate an API token to use to authenticate.
                Defaults to `CUBEJS_API_SECRET`.
            - query (dict, list, optional): `dict` or `list` representing
                valid CubeJS queries.
                If you pass multiple queries, then be aware of CubeJS Data Blending.
                More info at: https://cube.dev/docs/rest-api#api-reference-v-1-load
                and at: https://cube.dev/docs/schema/advanced/data-blending
                Query format can be found at: https://cube.dev/docs/query-format
            - security_context (str, dict, optional): The security context to use
                during authentication.
                If the security context does not contain an expiration period,
                then a 7 days expiration period is added automatically.
                More info at: https://cube.dev/docs/security/context

        Raises:
            - ValueError if both `subdomain` and `url` are missing.
            - ValueError if `api_token` is missing and `api_token_env_var` cannot be found.
            - ValueError if `query` is missing.
            - `prefect.engine.signals.FAIL` if the CubeJS Query API fails.

        Returns:
            - The CubeJS JSON response

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
                extended_context["epxiresIn"] = "7d"
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

        secs = 2
        while True:
            with session.get(url=query_api_url, params=params) as response:

                self.logger.debug(f"URL is: {response.url}")

                if response.status_code == 200:
                    data = response.json()

                    if "error" in data.keys() and "Continue wait" in data["error"]:
                        self.logger.warning(
                            f"CubeJS Query still running. Waiting {secs} seconds before retrying..."
                        )
                        time.sleep(secs)
                        secs *= 2 if secs < 60 else 2
                        continue

                    else:
                        return data

                else:
                    raise FAIL(
                        message=f"CubeJS Query API failed!. Error is: {response.reason}"
                    )
