import json
from time import sleep

import requests
import pendulum

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class AirbyteConnectionTask(Task):
    """
    Task for triggering Airbyte Connections, where "A connection is a configuration for syncing data between a source
    and a destination."
    See https://docs.airbyte.io/understanding-airbyte/connections

    This task assumes that the Airbyte Open-Source, since "For Airbyte Open-Source you don't need the API Token for
    Authentication! All endpoints are possible to access using the API without it."
    See https://docs.airbyte.io/api-documentation

    Args:
        - connection_id (str, optional): Default connection id to use for sync jobs, if none is specified to `run`.
        - **kwargs (Any, optional): additional kwargs to pass to the base Task constructor
    """

    CONNECTION_STATUS_ACTIVE = "active"

    def __init__(self, airbyte_server_host: str = "localhost", airbyte_server_port: int = 8000,
                 airbyte_api_version: str = "v1", connection_id: str = None, **kwargs):
        self.airbyte_server_host = airbyte_server_host
        self.airbyte_server_port = airbyte_server_port
        self.airbyte_api_version = airbyte_api_version
        self.connection_id = connection_id
        super().__init__(**kwargs)

    def parse_timestamp(self, api_time: str):
        """Returns either the pendulum-parsed actual timestamp or
        a very out-of-date timestamp if not set
        """
        return (
            pendulum.parse(api_time)
            if api_time is not None
            else pendulum.from_timestamp(-1)
        )

    def get_connection_status(self, session, airbyte_base_url, connection_id):
        get_connection_url = airbyte_base_url + "/connections/get/"

        # TODO - missing Auth ...
        # note - endpoint accepts application/json request body
        response = session.post(get_connection_url, json={"connectionId": connection_id})
        self.logger.info(response.json())
        connection_status = response.json()["status"]
        self.logger.info(
            f"Connection {connection_id}: status {connection_status}")
        return connection_status

    def trigger_manual_sync_connection(self, session, airbyte_base_url, connection_id):
        """
        Trigger a manual sync of the Connection, see:
        https://airbyte-public-api-docs.s3.us-east-2.amazonaws.com/rapidoc-api-docs.html#post-/v1/connections/sync

        Args:
            session:
            airbyte_base_url:
            connection_id:

        Returns:

        """
        get_connection_url = airbyte_base_url + "/connections/sync/"

        # TODO - missing Auth ...
        response = session.post(get_connection_url, json={"connectionId": connection_id})
        self.logger.info(response.json())
        created_at = response.json()["job"]["createdAt"]
        self.logger.info(
            f"Connection {connection_id}: created_at {created_at}")
        return created_at

    def get_connection_state(self, session, airbyte_base_url, connection_id):
        get_connection_url = airbyte_base_url + "/state/get/"

        # TODO - missing Auth ...
        response = session.post(get_connection_url, json={"connectionId": connection_id})
        self.logger.info(response.json())
        connection_state = response.json()["state"]
        self.logger.info(
            f"Connection {connection_id}: state {connection_state}")
        return connection_state

    @defaults_from_attrs("connection_id")
    def run(
        self,
        connection_id: str = None,
        poll_interval_s: int = 15,
    ) -> dict:
        """
        Task run method for triggering an Airbyte Connection.

        *It is assumed that the user will have previously configured a Source & Destination into a Connection.*
        e.g. MySql -> CSV

        An invocation of `run` will attempt to start a sync job for the specified `connection_id` representing the Connection in Airbyte.

        `run` will poll Airbyte Server for the Connection status and will only complete when the sync has completed or
        when it receives an error status code from an API call.

        Args:
            - connection_id (str, optional): if provided, will overwrite the value provided at init.
            - poll_interval_s (int, optional): this task polls the Airbyte API for status,
              if provided this value will override the default polling time of 15 seconds.

        Returns:
            - dict: connection_id (str) and succeeded_at (timestamp str)
        """
        if not connection_id:
            raise ValueError("Value for parameter `connection_id` *must* be provided.")

        # see https://airbyte-public-api-docs.s3.us-east-2.amazonaws.com/rapidoc-api-docs.html#overview
        airbyte_base_url = f"http://{self.airbyte_server_host}:{self.airbyte_server_port}/api/{self.airbyte_api_version}"

        self.logger.info(f"Getting Airbyte Connection {connection_id}, poll interval set to {poll_interval_s} seconds, airbyte_base_url {airbyte_base_url}")

        session = requests.Session()
        connection_status = self.get_connection_status(session, airbyte_base_url, connection_id)

        self.logger.info(f"connection_status {connection_status}")

        if connection_status == self.CONNECTION_STATUS_ACTIVE:
            # Trigger manual sync on the Connection ...
            self.trigger_manual_sync_connection(session, airbyte_base_url, connection_id)

            loop: bool = True
            # TODO - implement timeout? ...
            while loop:
                # get the Connection state ...
                connection_state = self.get_connection_state(session, airbyte_base_url, connection_id)
                self.logger.info(f"connection_state {connection_state}")
                if connection_state == "COMPLETED":
                    loop = False
                    
                # wait for next poll interval
                sleep(poll_interval_s)

            return {
                "connection_id": connection_id,
                "status": connection_status,
                "state": connection_state
            }
        else:
            return {
                "connection_id": connection_id,
                "status": connection_status
            }
