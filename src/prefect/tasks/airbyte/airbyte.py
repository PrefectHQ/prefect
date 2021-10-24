import re
from time import sleep

import requests
from requests import RequestException

from prefect import Task
from prefect.engine.signals import FAIL
from prefect.utilities.tasks import defaults_from_attrs


class ConnectionNotFoundException(Exception):
    pass


class AirbyteServerNotHealthyException(Exception):
    pass


class JobNotFoundException(Exception):
    pass


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

    # Connection statuses
    CONNECTION_STATUS_ACTIVE = "active"
    CONNECTION_STATUS_INACTIVE = "inactive"
    CONNECTION_STATUS_DEPRECATED = "deprecated"

    # Job statuses
    JOB_STATUS_SUCCEEDED = "succeeded"
    JOB_STATUS_FAILED = "failed"

    def __init__(
        self,
        airbyte_server_host: str = "localhost",
        airbyte_server_port: int = 8000,
        airbyte_api_version: str = "v1",
        connection_id: str = None,
        **kwargs,
    ):
        self.airbyte_server_host = airbyte_server_host
        self.airbyte_server_port = airbyte_server_port
        self.airbyte_api_version = airbyte_api_version
        self.connection_id = connection_id
        super().__init__(**kwargs)

    def check_health_status(self, session, airbyte_base_url):
        get_connection_url = airbyte_base_url + "/health/"
        try:
            response = session.get(get_connection_url)
            self.logger.info(response.json())
            health_status = response.json()["db"]
            if not health_status:
                raise AirbyteServerNotHealthyException(
                    f"Airbyte Server health status: {health_status}"
                )
            return True
        except RequestException as e:
            raise AirbyteServerNotHealthyException(e)

    def get_connection_status(self, session, airbyte_base_url, connection_id):
        get_connection_url = airbyte_base_url + "/connections/get/"

        # TODO - missing authentiction ...
        # note - endpoint accepts application/json request body
        try:
            response = session.post(
                get_connection_url, json={"connectionId": connection_id}
            )
            self.logger.info(response.json())

            # check whether a schedule exists ...
            schedule = response.json()["schedule"]
            if schedule:
                self.logger.warning("Found existing Connection schedule, removing ...")

                # mandatory fields for Connection update ...
                sync_catalog = response.json()["syncCatalog"]
                connection_status = response.json()["status"]

                update_connection_url = airbyte_base_url + "/connections/update/"
                response2 = session.post(
                    update_connection_url,
                    json={
                        "connectionId": connection_id,
                        "syncCatalog": sync_catalog,
                        "schedule": None,
                        "status": connection_status,
                    },
                )
                self.logger.info(response2.json())

                if response2.status_code == 200:
                    self.logger.info("Schedule removed ok.")
                else:
                    self.logger.warning("Schedule not removed.")

            connection_status = response.json()["status"]
            return connection_status
        except RequestException as e:
            raise AirbyteServerNotHealthyException(e)

    def trigger_manual_sync_connection(self, session, airbyte_base_url, connection_id):
        """
        Trigger a manual sync of the Connection, see:
        https://airbyte-public-api-docs.s3.us-east-2.amazonaws.com/rapidoc-api-docs.html#post-/v1/connections/sync

        Args:
            session:
            airbyte_base_url:
            connection_id:

        Returns: created_at - timestamp of sync job creation

        """
        get_connection_url = airbyte_base_url + "/connections/sync/"

        # TODO - missing authentication ...
        try:
            response = session.post(
                get_connection_url, json={"connectionId": connection_id}
            )
            if response.status_code == 200:
                self.logger.info(response.json())
                job_id = response.json()["job"]["id"]
                job_created_at = response.json()["job"]["createdAt"]
                return job_id, job_created_at
            elif response.status_code == 404:
                # connection_id not found
                self.logger.warn(
                    f"Connection {connection_id} not found, please double check the connection_id ..."
                )
                raise ConnectionNotFoundException(
                    f"Connection {connection_id} not found, please double check the connection_id ..."
                )
        except RequestException as e:
            raise AirbyteServerNotHealthyException(e)

    def get_job_status(self, session, airbyte_base_url, job_id):
        get_connection_url = airbyte_base_url + "/jobs/get/"

        # TODO - missing authentication ...
        try:
            response = session.post(get_connection_url, json={"id": job_id})
            if response.status_code == 200:
                self.logger.info(response.json())
                job_status = response.json()["job"]["status"]
                job_created_at = response.json()["job"]["createdAt"]
                job_updated_at = response.json()["job"]["updatedAt"]
                return job_status, job_created_at, job_updated_at
            elif response.status_code == 404:
                self.logger.error(f"Job {job_id} not found...")
                raise JobNotFoundException(f"Job {job_id} not found...")
        except RequestException as e:
            raise AirbyteServerNotHealthyException(e)

    @defaults_from_attrs("airbyte_server_host","airbyte_server_port","airbyte_api_version","connection_id")
    def run(
        self,
        airbyte_server_host: str,
        airbyte_server_port: int,
        airbyte_api_version: str,
        connection_id: str,
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
        # TODO - pass in the Airbyte connection info as well

        if not connection_id:
            raise ValueError("Value for parameter `connection_id` *must* be provided.")

        uuid = re.compile("^[0-9A-Fa-f-]+$")
        match = uuid.match(connection_id)
        if not match:
            raise ValueError(
                "Parameter `connection_id` *must* be a valid UUID i.e. 32 hex characters, including hyphens."
            )

        # see https://airbyte-public-api-docs.s3.us-east-2.amazonaws.com/rapidoc-api-docs.html#overview
        airbyte_base_url = f"http://{airbyte_server_host}:{airbyte_server_port}/api/{airbyte_api_version}"

        session = requests.Session()
        self.check_health_status(session, airbyte_base_url)
        self.logger.info(
            f"Getting Airbyte Connection {connection_id}, poll interval {poll_interval_s} seconds, airbyte_base_url {airbyte_base_url}"
        )

        connection_status = self.get_connection_status(
            session, airbyte_base_url, connection_id
        )
        if connection_status == self.CONNECTION_STATUS_ACTIVE:
            # Trigger manual sync on the Connection ...
            job_id, job_created_at = self.trigger_manual_sync_connection(
                session, airbyte_base_url, connection_id
            )

            while True:
                job_status, job_created_at, job_updated_at = self.get_job_status(
                    session, airbyte_base_url, job_id
                )

                # pending┃running┃incomplete┃failed┃succeeded┃cancelled
                if job_status == self.JOB_STATUS_SUCCEEDED:
                    self.logger.info(f"Job {job_id} succeeded.")
                    break
                elif job_status == self.JOB_STATUS_FAILED:
                    self.logger.error(f"Job {job_id} failed.")
                    break
                else:
                    # wait for next poll interval
                    sleep(poll_interval_s)

            return {
                "connection_id": connection_id,
                "status": connection_status,
                "job_status": job_status,
                "job_created_at": job_created_at,
                "job_updated_at": job_updated_at,
            }
        elif connection_status == self.CONNECTION_STATUS_INACTIVE:
            self.logger.error(
                f"Please enable the Connection {connection_id} in Airbyte Server."
            )
            raise FAIL(
                f"Please enable the Connection {connection_id} in Airbyte Server."
            )
        elif connection_status == self.CONNECTION_STATUS_DEPRECATED:
            self.logger.error(f"Connection {connection_id} is deprecated.")
            raise FAIL(f"Connection {connection_id} is deprecated.")
