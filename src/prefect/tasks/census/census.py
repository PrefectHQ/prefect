import time

import re
import requests

from prefect import Task
from prefect.utilities.tasks import defaults_from_attrs


MIN_WAIT_TIME, DEFAULT_WAIT_TIME = 5, 60


class CensusSyncTask(Task):
    """
    Task for running Census connector sync jobs.

    This task assumes the user has a Census sync already configured and is attempting to orchestrate the
    sync using Prefect task to send a post to the API within a prefect flow. Copy and paste from the api
    trigger section on the configuration page in the `api_trigger` param to set a default sync.

    Args:
        - api_trigger (str, optional): Default sync to trigger, if none is specified in `run`. The API
            trigger URL for a sync can be found on sync's configuration page
            (https://app.getcensus.com/syncs/{sync_id}/configuration) under Sync Triggers > API.
        - **kwargs (dict, optional): Additional kwargs to pass to the base Task constructor.

    Example:
        Trigger a Census sync with an `api_trigger` stored in a Prefect secret:
        ```python
        from prefect import Flow
        from prefect.tasks.census import CensusSyncTask
        from prefect.tasks.secrets import PrefectSecret

        sync_census = CensusSyncTask()

        with Flow("Run Census Sync") as flow:
            api_trigger = PrefectSecret('CENSUS_API_TRIGGER')
            results = sync_census(api_trigger=api_trigger)
        ```
    """

    def __init__(self, api_trigger=None, **kwargs):
        if api_trigger:
            self.check_invalid_api(api_trigger)
        self.api_trigger = api_trigger
        super().__init__(**kwargs)

    @defaults_from_attrs("api_trigger")
    def run(
        self, api_trigger: str, poll_status_every_n_seconds: int = DEFAULT_WAIT_TIME
    ) -> dict:
        """
        Task run method for Census syncs.

        An invocation of `run` will attempt to start a sync job for the specified `api_trigger`. `run`
        will poll Census for the sync status, and will only complete when the sync has completed or
        when it receives an error status code from the trigger API call.

        Args:
            - api_trigger (str): Ff not specified in run, it will pull from the default for the
                CensusSyncTask constructor. The API trigger URL for a sync can be found on sync's
                configuration page (https://app.getcensus.com/syncs/{sync_id}/configuration) under
                Sync Triggers > API.
            - poll_status_every_n_seconds (int, optional): This task polls the Census API for the sync's
                status. If provided, this value will override the default polling time of
                60 seconds and it has a minimum wait time of 5 seconds. Keyword argument.

        Returns:
            - dict: Dictionary of statistics returned by Census on the specified sync in
                following structure:
                ```python
                {
                    'error_message': None / str,
                    'records_failed': int / None,
                    'records_invalid': int / None,
                    'records_processed': int / None,
                    'records_updated': int / None,
                    'status': 'completed'/'working'/'failed'
                }
                ```
        """

        if not api_trigger:
            raise ValueError(
                """Value for parameter `api_trigger` must be provided. See Census sync
                                configuration page."""
            )

        confirmed_pattern = self.check_invalid_api(api_trigger)

        secret, sync_id = confirmed_pattern.groups()
        response = requests.post(api_trigger)
        response.raise_for_status()

        sleep_time = max(MIN_WAIT_TIME, poll_status_every_n_seconds)

        self.logger.debug(
            f"Started Census sync {sync_id}, sleep time set to {sleep_time} seconds."
        )

        sync_run_id = response.json()["data"]["sync_run_id"]
        sr_url = f"https://bearer:secret-token:{secret}@app.getcensus.com/api/v1/sync_runs/{sync_run_id}"
        log_url = f"https://app.getcensus.com/syncs/{sync_id}/sync-history"

        result = {}

        start_time = time.time()
        while True:
            time.sleep(sleep_time)
            status_response = requests.get(sr_url)
            response_dict = status_response.json()
            if status_response.status_code != 200 or "data" not in response_dict.keys():
                raise ValueError(
                    f"Getting status of sync failed, please visit Census Logs at {log_url} to see more."
                )
            result = response_dict["data"]
            status = result["status"]
            if status == "working":
                self.logger.debug(
                    f"Sync {sync_id} still running after {round(time.time()-start_time, 2)} seconds."
                )
                continue
            break

        self.logger.debug(
            f"Sync {sync_id} has finished running after {round(time.time()-start_time, 2)} seconds."
        )

        self.logger.info(f"View sync details here: {log_url}.")

        return result

    @staticmethod
    def check_invalid_api(api_trigger: str):
        """
        Makes sure the URL for the API trigger matches the Census format specified below. If it does
        not, it will raise a ValueError.

        Format of api_trigger:
            - https://bearer:secret-token:{secret}@app.getcensus.com/api/v1/syncs/{sync_id}/trigger

        Args:
            - api_trigger (str): If specified in the constructor, will call this validation there

        Returns:
            - confirmed_pattern (Match Object - https://docs.python.org/3/library/re.html#match-objects)
        """
        pattern = r"https:\/\/bearer:secret-token:(.*)@app.getcensus.com\/api\/v1\/syncs\/(\d*)\/trigger"
        url_pattern = re.compile(pattern)
        # Making sure it is a valid api trigger.
        confirmed_pattern = url_pattern.match(api_trigger)

        if not confirmed_pattern:
            raise ValueError(
                """Invalid parameter for `api_trigger` please paste directly from the Census
                                sync configuration page. This is CaSe SenSITiVe."""
            )
        return confirmed_pattern
