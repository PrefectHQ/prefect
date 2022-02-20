import jwt
from requests import Session
import time
from typing import Dict, Union

from prefect.engine.signals import FAIL

# Cube Cloud base URL
__CUBEJS_CLOUD_BASE_URL = "https://{subdomain}.cubecloud.dev"


def get_cube_base_url(subdomain: str, url: str) -> str:
    """
    Get Cube.js base URL.

    Args:
        - subdomain (str): Cube Cloud subdomain.
        - url (str): Cube API url.

    Returns:
        - Cube.js API base url.
    """
    cube_base_url = __CUBEJS_CLOUD_BASE_URL
    if subdomain:
        cube_base_url = f"{cube_base_url.format(subdomain=subdomain)}/cubejs-api"
    else:
        cube_base_url = url
    return cube_base_url


def get_query_api_url(subdomain: str, url: str) -> str:
    """
    Get Cube.js Query API URL.

    Args:
        - subdomain (str): Cube Cloud subdomain.
        - url (str): Cube API url.

    Returns:
        - Cube.js Query API URL.
    """
    return f"{get_cube_base_url(subdomain=subdomain, url=url)}/v1/load"


def get_sql_api_url(subdomain: str, url: str) -> str:
    """
    Get Cube.js Query SQL API URL.

    Args:
        - subdomain (str): Cube Cloud subdomain.
        - url (str): Cube API url.

    Returns:
        - Cube.js Query SQL API URL.
    """
    return f"{get_cube_base_url(subdomain=subdomain, url=url)}/v1/sql"


def get_api_token(security_context: Union[str, Dict], secret: str) -> str:
    """
    Build API Token given the security context and the secret.

    Args:
        - security_context (str, dict): The security context to use
            to retrieve data from Cube.js.
        - secret (str): The secret key to use to interact with Cube.js APIs.

    Returns:
        - The API Token to include in the authorization headers
            when calling Cube.js APIs.
    """
    api_token = jwt.encode(payload={}, key=secret)
    if security_context:

        extended_context = security_context
        if "exp" not in security_context and "expiresIn" not in security_context:
            extended_context["expiresIn"] = "7d"
        api_token = jwt.encode(payload=extended_context, key=secret, algorithm="HS256")

    return api_token


def get_data_from_url(
    api_token: str, url: str, params: Dict, max_wait_time: int, wait_api_call_secs: int
) -> Dict:
    """
    Retrieve data from a Cube.js API.

    Args:
        - api_token (str): The API Token to include in the authorization headers
            when calling Cube API.
        - url (str): The URL of the Cube API to call.
        - max_wait_time (int): The number of seconds to wait for the
            Cube.js load API to return a response.
        - wait_api_call_secs (int): The number of seconds to
            wait between API calls.
    """
    session = Session()
    session.headers = {
        "Content-type": "application/json",
        "Authorization": api_token,
    }
    elapsed_wait_time = 0
    while not max_wait_time or elapsed_wait_time <= max_wait_time:

        with session.get(url=url, params=params) as response:

            if response.status_code == 200:
                data = response.json()

                if "error" in data.keys() and "Continue wait" in data["error"]:
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
