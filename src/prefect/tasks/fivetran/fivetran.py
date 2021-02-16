import json
import time

import requests
import pendulum

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


class FivetranSyncTask(Task):
    """
    Task for running Fivetran connector sync jobs.

    This task assumes the user is a Fivetran user (https://fivetran.com) who has
    successfully setup a connector and has access to the API credentials for
    that user (https://fivetran.com/account/settings, "API Config").

    Args:
        - connector_id (str, optional): Default connector id to use for sync jobs, if none is
            specified to `run`.
        - **kwargs (Any, optional): additional kwargs to pass to the base Task constructor
    """

    def __init__(self, connector_id: str = None, **kwargs):
        self.connector_id = connector_id
        super().__init__(**kwargs)

    @defaults_from_attrs("connector_id")
    def run(
        self,
        api_key: str,
        api_secret: str,
        connector_id: str = None,
        poll_status_every_n_seconds: int = 15,
    ) -> dict:
        """
        Task run method for Fivetran connector syncs.

        An invocation of `run` will attempt to start a sync job for the specified `connector_id`. `run`
        will poll Fivetran for connector status, and will only complete when the sync has completed or
        when it receives an error status code from an API call.

        Args:
            - api_key (str): `API key` per https://fivetran.com/account/settings; should be secret!
            - api_secret (str): `API secret` per https://fivetran.com/account/settings; should be secret!
            - connector_id (str, optional): if provided, will overwrite value provided at init.
            - poll_status_every_n_seconds (int, optional): this task polls the Fivetran API for status,
                if provided this value will override the default polling time of 15 seconds.

        Returns:
            - dict: connector_id (str) and succeeded_at (timestamp str)
        """

        def parse_timestamp(api_time: str):
            """Returns either the pendulum-parsed actual timestamp or
            a very out-of-date timestamp if not set
            """
            return (
                pendulum.parse(api_time)
                if api_time is not None
                else pendulum.from_timestamp(-1)
            )

        if not connector_id:
            raise ValueError("Value for parameter `connector_id` must be provided.")
        if not api_key:
            raise ValueError("Value for parameter `api_key` must be provided.")
        if not api_secret:
            raise ValueError("Value for parameter `api_secret` must be provided.")

        URL_CONNECTOR: str = "https://api.fivetran.com/v1/connectors/{}".format(
            connector_id
        )

        self.logger.info(
            "Attempting start of Fivetran connector {}, sleep time set to {} seconds.".format(
                connector_id, poll_status_every_n_seconds
            )
        )

        # Automatically call `raise_for_status` on every request
        session = requests.Session()
        session.hooks = {"response": lambda r, *args, **kwargs: r.raise_for_status()}
        # Make sure connector configuration has been completed successfully and is not broken.
        resp = session.get(URL_CONNECTOR, auth=(api_key, api_secret))
        connector_details = resp.json()["data"]
        URL_LOGS = "https://fivetran.com/dashboard/connectors/{}/{}/logs".format(
            connector_details["service"], connector_details["schema"]
        )
        URL_SETUP = "https://fivetran.com/dashboard/connectors/{}/{}/setup".format(
            connector_details["service"], connector_details["schema"]
        )
        setup_state = connector_details["status"]["setup_state"]
        if setup_state != "connected":
            EXC_SETUP: str = (
                'Fivetran connector "{}" not correctly configured, status: {}; '
                + "please complete setup at {}"
            )
            raise ValueError(EXC_SETUP.format(connector_id, setup_state, URL_SETUP))
        # We need to know the previous job's completion time to know if the job succeeded or failed
        succeeded_at = parse_timestamp(connector_details["succeeded_at"])
        failed_at = parse_timestamp(connector_details["failed_at"])
        previous_completed_at = succeeded_at if succeeded_at > failed_at else failed_at
        # URL for connector logs within the UI
        self.logger.info(
            "Connector type: {}, connector schema: {}".format(
                connector_details["service"], connector_details["schema"]
            )
        )
        self.logger.info("Connectors logs at {}".format(URL_LOGS))

        # Set connector to manual sync mode, required to force sync through the API
        resp = session.patch(
            URL_CONNECTOR,
            data=json.dumps({"schedule_type": "manual"}),
            headers={"Content-Type": "application/json;version=2"},
            auth=(api_key, api_secret),
        )
        # Start connector sync
        resp = session.post(URL_CONNECTOR + "/force", auth=(api_key, api_secret))

        loop: bool = True
        while loop:
            resp = session.get(URL_CONNECTOR, auth=(api_key, api_secret))
            current_details = resp.json()["data"]
            # Failsafe, in case we missed a state transition – it is possible with a long enough
            # `poll_status_every_n_seconds` we could completely miss the 'syncing' state
            succeeded_at = parse_timestamp(current_details["succeeded_at"])
            failed_at = parse_timestamp(current_details["failed_at"])
            current_completed_at = (
                succeeded_at if succeeded_at > failed_at else failed_at
            )
            # The only way to tell if a sync failed is to check if its latest failed_at value
            # is greater than then last known "sync completed at" value.
            if failed_at > previous_completed_at:
                raise ValueError(
                    'Fivetran sync for connector "{}" failed; please see logs at {}'.format(
                        connector_id, URL_LOGS
                    )
                )
            # Started sync will spend some time in the 'scheduled' state before
            # transitioning to 'syncing'.
            # Capture the transition from 'scheduled' to 'syncing' or 'rescheduled',
            # and then back to 'scheduled' on completion.
            sync_state = current_details["status"]["sync_state"]
            self.logger.info(
                'Connector "{}" current sync_state = {}'.format(
                    connector_id, sync_state
                )
            )
            if current_completed_at > previous_completed_at:
                loop = False
            else:
                time.sleep(poll_status_every_n_seconds)

        return {
            "succeeded_at": succeeded_at.to_iso8601_string(),
            "connector_id": connector_id,
        }
