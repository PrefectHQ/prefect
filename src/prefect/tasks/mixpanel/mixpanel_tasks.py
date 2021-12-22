from datetime import date
from prefect import Task
import prefect
from prefect.utilities.tasks import defaults_from_attrs

import json
import os
import requests
from requests.auth import HTTPBasicAuth

from typing import Union, List


class MixpanelExportTask(Task):
    """
    Task for performing an export using Mixpanel Export API
    More info about the API can be found at https://developer.mixpanel.com/reference/raw-event-export

    Args:
        - api_secret (str, optional): the API secret key to use to authenticate
            to Mixpanel. Can be provided also via env var.
        - api_secret_env_var (str, optional): The name of the env var that contains
            the API secret key to use to authenticate to Mixpanel.
            `api_secret` takes precedence over `api_secret_env_var`.
        - from_date (str, optional): Start date of the export request.
            If provided as a string, it should be in the format `YYYY-MM-DD`
            Default value is `1900-01-01`. This date is inclusive.
        - to_date (str, optional): End date of the export request.
            If provided as a string, it should be in the format `YYYY-MM-DD`
            Default value is `prefect.context.today`. This date is inclusive
        - limit (int, optional): The max number of events to return.
        - event (str, list, optional): The event, or events, that you wish
            to get the data for.
        - where (str, optional): An expression to filter events by.
            More info on expression sequence structure can be found
            at https://developer.mixpanel.com/reference/segmentation-expressions
        - parse_response (bool, optional): Whether to parse the response into a JSON object
            Default value is `False`.
        - use_eu_server (bool, optional): Whether to use the Mixpanel EU server to retrieve data.
            More info at https://help.mixpanel.com/hc/en-us/articles/360039135652-Data-Residency-in-EU
            Default to `False`
        - **kwargs (dict, optional): additional keyword arguments to pass to the
            Task constructor
    """

    def __init__(
        self,
        api_secret: str = None,
        api_secret_env_var: str = None,
        from_date: str = "1900-01-01",
        to_date: str = date.today().strftime("%Y-%m-%d"),
        limit: int = None,
        event: Union[str, List[str]] = None,
        where: str = None,
        parse_response: bool = False,
        use_eu_server: bool = False,
        **kwargs
    ):
        self.api_secret = api_secret
        self.api_secret_env_var = api_secret_env_var
        self.from_date = from_date
        self.to_date = to_date
        self.limit = limit
        self.event = event
        self.where = where
        self.parse_response = parse_response
        self.use_eu_server = use_eu_server
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "api_secret",
        "api_secret_env_var",
        "from_date",
        "to_date",
        "limit",
        "event",
        "where",
        "parse_response",
        "use_eu_server",
    )
    def run(
        self,
        api_secret: str = None,
        api_secret_env_var: str = None,
        from_date: str = None,
        to_date: str = None,
        limit: int = None,
        event: Union[str, List[str]] = None,
        where: str = None,
        parse_response: bool = False,
        use_eu_server: bool = False,
    ):
        """
        Task run method to request a data export to Mixpanel using Export API

        Args:
            - api_secret (str, optional): the API secret key to use to authenticate
                to Mixpanel. Can be provided also via env var.
            - api_secret_env_var (str, optional): The name of the env var that contains
                the API secret key to use to authenticate to Mixpanel.
                `api_secret` takes precedence over `api_secret_env_var`.
            - from_date (str, optional): Start date of the export request.
                If provided as a string, it should be in the format `YYYY-MM-DD`
                Default value is `1900-01-01`. This date is inclusive.
            - to_date (str, optional): End date of the export request.
                If provided as a string, it should be in the format `YYYY-MM-DD`
                Default value is `prefect.context.today`. This date is inclusive
            - limit (int, optional): The max number of events to return.
            - event (str, list, optional): The event, or events, that you wish
                to get the data for.
            - where (str, optional): An expression to filter events by.
                More info on expression sequence structure can be found
                at https://developer.mixpanel.com/reference/segmentation-expressions
            - parse_response (bool, optional): Whether to parse the response into a JSON object
                Default value is `False`.
            - use_eu_server (bool, optional): Whether to use the Mixpanel EU server to retrieve data.
                More info at
                https://help.mixpanel.com/hc/en-us/articles/360039135652-Data-Residency-in-EU
                Default to `False`

        Returns:
            - if `parse_response` is `False` then returns the string response pulled
                from the Export API, (which is basically a JSONL string)
                else a JSON array obtained by parsing the raw response.

        Raises:
            - ValueError if both `api_secret` and `api_secret_env_var` are missing.
            - ValueError if `api_secret` is missing and `api_secret_env_var` is not found.

        """
        if not api_secret and not api_secret_env_var:
            raise ValueError("Missing both `api_secret` and `api_secret_env_var`.")
        elif not api_secret and api_secret_env_var not in os.environ:
            raise ValueError("Missing `api_secret` and `api_secret_env_var` not found.")

        secret = None
        if api_secret:
            self.logger.debug("Got secret from `api_secret`")
            secret = api_secret
        else:
            self.logger.debug(
                "Got secret from env var passed from `api_secret_env_var`"
            )
            secret = os.environ[api_secret_env_var]

        params = {"from_date": from_date, "to_date": to_date}

        if limit:
            params["limit"] = limit

        if event:
            params["event"] = json.dumps([event] if isinstance(event, str) else event)

        if where:
            params["where"] = where

        url = "https://{server}.mixpanel.com/api/2.0/export".format(
            server="data-eu" if use_eu_server else "data"
        )

        response = requests.get(
            url=url,
            auth=HTTPBasicAuth(secret, ""),
            headers={"Accept": "application/json"},
            params=params,
        )

        events = response.text

        ret = None
        if parse_response:
            if events:
                ret = [json.loads(event) for event in events.splitlines()]
        else:
            ret = events if events else None

        return ret
