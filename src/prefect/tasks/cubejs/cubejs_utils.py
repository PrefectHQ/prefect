import jwt
from requests import Session
import time
from typing import Dict, Union

from prefect.engine.signals import FAIL


class CubeJSClient:

    # Cube Cloud base URL
    __CUBEJS_CLOUD_BASE_URL = "https://{subdomain}.cubecloud.dev"

    def __init__(
        self,
        subdomain: str,
        url: str,
        security_context: Union[str, Dict],
        secret: str,
        wait_api_call_secs: int,
        max_wait_time: int,
    ):
        """
        Initialize a `CubeJSClient`.
        The client can be used to interact with Cube.js APIs.

        Args:
            - subdomain (str): Cube Cloud subdomain.
            - url (str): Cube.js URL (likely to be used in self-hosted Cube.js
                deployments).
            - security_context (str, dict): The security context to be used
                when interacting with Cube.js APIs.
            - secret (str): The secret string to be used, together with the
                `security_context`, to generate the API token to pass in the
                authorization header.
            - wait_api_call_secs (int): Number of seconds to wait
                between API calls.
            - max_wait_time (int): The maximum amount of seconds to wait for
                an API call to respond.
        """
        self.subdomain = subdomain
        self.url = url
        self.security_context = security_context
        self.secret = secret
        self.cube_base_url = self._get_cube_base_url()
        self.api_token = self.get_api_token()
        self.query_api_url = self._get_query_api_url()
        self.generated_sql_api_url = self._get_generated_sql_api_url()
        self.wait_api_call_secs = wait_api_call_secs
        self.max_wait_time = max_wait_time

    def _get_cube_base_url(self) -> str:
        """
        Get Cube.js base URL.

        Returns:
            - Cube.js API base url.
        """
        cube_base_url = self.__CUBEJS_CLOUD_BASE_URL
        if self.subdomain:
            cube_base_url = (
                f"{cube_base_url.format(subdomain=self.subdomain)}/cubejs-api"
            )
        else:
            cube_base_url = self.url
        return cube_base_url

    def _get_query_api_url(self) -> str:
        """
        Get Cube.js Query API URL.

        Returns:
            - Cube.js Query API URL.
        """
        return f"{self.cube_base_url}/v1/load"

    def _get_generated_sql_api_url(self) -> str:
        """
        Get Cube.js Query SQL API URL.

        Returns:
            - Cube.js Query SQL API URL.
        """

        return f"{self.cube_base_url}/v1/sql"

    def get_api_token(self) -> str:
        """
        Build API Token given the security context and the secret.

        Returns:
            - The API Token to include in the authorization headers
                when calling Cube.js APIs.
        """
        api_token = jwt.encode(payload={}, key=self.secret)
        if self.security_context:

            extended_context = self.security_context
            if (
                "exp" not in self.security_context
                and "expiresIn" not in self.security_context
            ):
                extended_context["expiresIn"] = "7d"
            api_token = jwt.encode(
                payload=extended_context, key=self.secret, algorithm="HS256"
            )

        return api_token

    def _get_data_from_url(self, api_url: str, params: Dict) -> Dict:
        """
        Retrieve data from a Cube.js API.

        Args:
            - api_url (str): The URL of the Cube API to call.
            - params (dict): Parameters to be passed to the API call.

        Raises:
            - `prefect.engine.signals.FAIL` if the response has `status_code != 200`.
            - `prefect.engine.signals.FAIL` if the REST APIs takes too long to respond,
                with regards to `max_wait_time`.

        Returns:
            - Cube.js REST API JSON response
        """
        session = Session()
        session.headers = {
            "Content-type": "application/json",
            "Authorization": self.api_token,
        }
        elapsed_wait_time = 0
        while not self.max_wait_time or elapsed_wait_time <= self.max_wait_time:

            with session.get(url=api_url, params=params) as response:
                if response.status_code == 200:
                    data = response.json()

                    if "error" in data.keys() and "Continue wait" in data["error"]:
                        time.sleep(self.wait_api_call_secs)
                        elapsed_wait_time += self.wait_api_call_secs
                        continue

                    else:
                        return data

                else:
                    raise FAIL(
                        message=f"Cube.js load API failed! Error is: {response.reason}"
                    )
        msg = f"Cube.js load API took longer than {self.max_wait_time} seconds to provide a response."
        raise FAIL(message=msg)

    def get_data(
        self,
        params: Dict,
        include_generated_sql: bool,
    ) -> Dict:
        """
        Retrieve data from Cube.js `/load` REST API.

        Args:
            - params (dict): Parameters to pass to the `/load` REST API.
            - include_generated_sql (bool): Whether to include the
                corresponding generated SQL or not.

        Returns:
            - Cube.js `/load` API JSON response, augmented with SQL
                information if `include_generated_sql` is `True`.
        """
        data = self._get_data_from_url(api_url=self.query_api_url, params=params)

        if include_generated_sql:
            data["sql"] = self._get_data_from_url(
                api_url=self.generated_sql_api_url, params=params
            )["sql"]

        return data
