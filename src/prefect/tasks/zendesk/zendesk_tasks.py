from collections import defaultdict
from datetime import datetime
import os

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs
from prefect.engine.signals import FAIL

import requests
import time
from typing import List, Union


class ZendeskTicketsIncrementalExportTask(Task):
    """
    This task can be used to perform an incremental export of tickets from Zendesk.
    More info at
    https://developer.zendesk.com/api-reference/ticketing/ticket-management/incremental_exports/#incremental-ticket-export.

    Args:
        - subdomain (str, optional): The Zendesk subdomain to use to export tickets.
        - email_address (str, optional): The email address to use to authenticate on Zendesk.
        - api_token (str, optional): The API token to use to athenticate on Zendesk
            If passed, it will take precedence over `api_token_env_var`.
        - api_token_env_var (str, optional): The name of the env var which contains the
            API token to use to authenticate on Zendesk.
        - start_time (int, datetime, optional): The start time to use to export tickets.
            Can be passed as an epoch timestamp or a `datetime` object.
        - cursor (str, optional): The cursor to use to export tickets.
            If passed, it will take precedence over `start_time`.
        - exclude_deleted: (bool, optional): Whether to exclude deleted tickets or not.
            Default to `False`.
        - include_entities: (str, list, optional): Optional list of entities to side load.
          More info at
          https://developer.zendesk.com/documentation/ticketing/using-the-zendesk-api/side_loading/.
        - **kwargs (dict, optional): Additional keyword arguments to pass to the
            Task constructor.
    """

    _ZENDESK_API_BASE_URL = "https://{subdomain}.zendesk.com/api/v2"

    def __init__(
        self,
        subdomain: str = None,
        email_address: str = None,
        api_token: str = None,
        api_token_env_var: str = None,
        start_time: Union[int, datetime] = None,
        cursor: str = None,
        exclude_deleted: bool = False,
        include_entities: List[str] = None,
        **kwargs,
    ):
        self.subdomain = subdomain
        self.email_address = email_address
        self.api_token = api_token
        self.api_token_env_var = api_token_env_var
        self.start_time = start_time
        self.cursor = cursor
        self.exclude_deleted = exclude_deleted
        self.include_entities = include_entities
        super().__init__(**kwargs)

    @defaults_from_attrs(
        "subdomain",
        "email_address",
        "api_token",
        "api_token_env_var",
        "start_time",
        "cursor",
        "exclude_deleted",
        "include_entities",
    )
    def run(
        self,
        subdomain: str = None,
        email_address: str = None,
        api_token: str = None,
        api_token_env_var: str = None,
        start_time: Union[int, datetime] = None,
        cursor: str = None,
        exclude_deleted: bool = None,
        include_entities: List[str] = None,
    ):
        """
        Task run method to perform an incremental export of tickets from Zendesk.
        Args:
            - subdomain (str, optional): The Zendesk subdomain to use to export tickets.
            - email_address (str, optional): The email address to use to authenticate on Zendesk.
            - api_token (str, optional): The API token to use to athenticate on Zendesk
                If passed, it will take precedence over `api_token_env_var`.
            - api_token_env_var (str, optional): The name of the env var which contains the
                API token to use to authenticate on Zendesk.
            - start_time (int, datetime, optional): The start time to use to export tickets.
                Can be passed as an epoch timestamp or a `datetime` object.
            - cursor (str, optional): The cursor to use to export tickets.
                If passed, it will take precedence over `start_time`.
            - exclude_deleted: (bool, optional): Whether to exclude deleted tickets or not.
                Default to `False`.
            - include_entities: (str, list, optional): Optional list of entities to side load.
                More info at
                https://developer.zendesk.com/documentation/ticketing/using-the-zendesk-api/side_loading/.

        Raises:
            - `ValueError` if both `api_token` and `api_token_env_var` are missing.
            - `ValueError` if `api_token` is missing and `api_token_env_var` cannot be found.
            - `ValueError` if `subdomain` is missing.
            - `ValueError` if `email_address` is missing.
            - `ValueError` if both `start_time` and `cursor` are missing.
            - `prefect.engine.signals.FAIL` if the Zendesk API call fails.

        Returns:
            - A `dict` containing the list of tickets and, optionally, the included
              entities.
        """
        if not api_token and not api_token_env_var:
            raise ValueError("Both `api_token` and `api_token_env_var` are missing.")

        if not api_token and api_token_env_var not in os.environ:
            raise ValueError(
                "`api_token` is missing and `api_token_env_var` not found."
            )

        token = None
        if api_token:
            token = api_token
        elif api_token_env_var:
            token = os.environ[api_token_env_var]

        if not subdomain:
            raise ValueError("`subdomain` is missing.")

        if not email_address:
            raise ValueError("`email_address` is missing.")

        if not start_time and not cursor:
            raise ValueError("Both `start_time` and `cursor` are missing.")

        base_url = self._ZENDESK_API_BASE_URL.format(subdomain=subdomain)
        export_url = f"{base_url}/incremental/tickets/cursor.json"

        if cursor:
            self.logger.debug("Got cursor")
            export_url = f"{export_url}?cursor={cursor}"

        elif start_time:
            self.logger.debug("Got start_time")
            start_datetime = (
                start_time
                if isinstance(start_time, int)
                else int(start_time.timestamp())
            )
            export_url = f"{export_url}?start_time={start_datetime}"

        if exclude_deleted:
            export_url = f"{export_url}&exclude_deleted=true"

        if include_entities:
            if isinstance(include_entities, str):
                include_entities_str = include_entities
            elif isinstance(include_entities, list):
                include_entities_str = ",".join(list(set(include_entities)))

            export_url = f"{export_url}&include={include_entities_str}"

        session = requests.Session()
        session.auth = f"{email_address}/token", token

        end_of_stream = False

        tickets = defaultdict(list)

        while not end_of_stream:
            with session.get(export_url) as response:
                self.logger.debug(f"Export URL is: {export_url}")

                if response.status_code == 429:
                    retry_after_seconds = int(response.headers["retry-after"])
                    self.logger.warning(
                        f"""
                        API rate limit reached!
                        Waiting for {retry_after_seconds} seconds before retrying.
                        """
                    )
                    time.sleep(retry_after_seconds + 1)
                    continue

                elif response.status_code != 200:
                    msg = f"""
                    Zendesk API call failed!
                    Status: {response.status_code}
                    Reason: {response.reason}
                    """
                    raise FAIL(message=msg)

                content = response.json()

                tickets["tickets"].extend(content["tickets"])

                if include_entities:
                    for include_entity in list(set(include_entities)):
                        if include_entity in content.keys():
                            tickets[include_entity].extend(content[include_entity])

                end_of_stream = content["end_of_stream"]
                export_url = content["after_url"]
                cursor = content["after_cursor"]

            if not end_of_stream:
                # Try to avoid the rate limit: 10 requests per minute
                time.sleep(0.1)

        return tickets
