from requests import Session
import time
from typing import Dict

from prefect.engine.signals import FAIL


class HightouchClient:

    __HIGHTOUCH_BASE_URL = "https://api.hightouch.io"
    __HIGHTOUCH_START_NEW_SYNC_RUN_URL = f"{__HIGHTOUCH_BASE_URL}/api/v2/rest/run"
    __HIGHTOUCH_GET_SYNC_RUN_STATUS = f"{__HIGHTOUCH_BASE_URL}/api/v2/rest/sync"

    def __init__(self, api_key: str):
        """
        Create an `HightouchClient`.

        Args:
            - api_key (str): The API kye to use to authenticate API calls on Hightouch.
        """
        self.api_key = api_key
        self.session = Session()
        self.session.headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_sync_run_status(self, sync_id: int) -> Dict:
        """
        Return the status of a sync run.
        The status is obtained by calling the
        [Get sync run status API](https://hightouch.io/docs/syncs/api/#get-the-status-of-a-sync-run).

        Args:
            - sync_id (int): The sync identifier.

        Raises:
            - `prefect.engine.signals.FAIL` if the response status code is not 200.

        Returns:
            - The JSON response containing information about the status of
                the sync run.
        """
        url = f"{self.__HIGHTOUCH_GET_SYNC_RUN_STATUS}/{sync_id}"
        with self.session.get(url) as response:
            if response.status_code != 200:
                msg = f"Error while retrieving sync run status. Error is: {response.reason}."
                raise FAIL(message=msg)

            return response.json()

    def start_sync_run(
        self,
        sync_id: int,
        wait_for_completion: bool,
        wait_time_between_api_calls: int,
        max_wait_time: int,
    ) -> Dict:
        """
        Start a new sync run.
        Optionally, wait for run completion.
        The sync run is triggered via the
        [Start new sync run API](https://hightouch.io/docs/syncs/api/#start-a-new-sync-run).

        Args:
            - sync_id (int): The sync identifier.
            - wait_for_completion (bool): Whether to wait for the sync run completion or not.
            - wait_time_between_api_calls (int): The number of seconds to wait between API calls.
                This is used only if `wait_for_completion` is `True`.
            - max_wait_time (int): The maximum number of seconds to wait for the sync run to complete.
                This is used only if `wait_for_completion` is `True`.

        Raises:
            - `prefect.engine.signals.FAIL` if the sync run takes more
                than `max_wait_time` seconds to complete.

        Returns:
            - If `wait_for_completion` is `True`, returns the JSON response
                containing the status of the sync run.
            - If `wait_for_completion` is `False`, returns the JSON response
                containing information about the start sync run action.
        """
        url = f"{self.__HIGHTOUCH_START_NEW_SYNC_RUN_URL}/{sync_id}"
        with self.session.post(url) as response:
            if response.status_code != 200:
                msg = f"Error while starting sync run. Error is: {response.reason}."
                raise FAIL(message=msg)

            start_sync_response = response.json()
            if wait_for_completion:
                elapsed_wait_time = 0
                sync_status = None
                while not max_wait_time or elapsed_wait_time <= max_wait_time:

                    sync_status_response = self.get_sync_run_status(sync_id=sync_id)
                    sync_status = sync_status_response["sync"]["sync_status"]

                    if sync_status == "success":
                        return sync_status_response
                    else:
                        time.sleep(wait_time_between_api_calls)
                        elapsed_wait_time += wait_time_between_api_calls

                msg = "Sync run exceeded `max_wait_time`"
                raise FAIL(message=msg)

            else:
                return start_sync_response
