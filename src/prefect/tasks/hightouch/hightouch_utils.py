from requests import Session
import time
from typing import Dict

from prefect.engine.signals import FAIL
import prefect


class HightouchClient:

    __HIGHTOUCH_BASE_URL = "https://api.hightouch.io"
    __HIGHTOUCH_START_NEW_SYNC_RUN_URL = f"{__HIGHTOUCH_BASE_URL}/api/v2/rest/run"
    __HIGHTOUCH_GET_SYNC_RUN_STATUS = f"{__HIGHTOUCH_BASE_URL}/api/v2/rest/sync"

    def __init__(self, api_key: str):
        """
        TODO
        """
        self.api_key = api_key
        self.session = Session()
        self.session.headers = {
            "Content-type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def get_sync_run_status(self, sync_id: int) -> Dict:
        """
        TODO
        """
        url = f"{self.__HIGHTOUCH_GET_SYNC_RUN_STATUS}/{sync_id}"
        with self.session.get(url) as response:
            if response.status_code != 200:
                msg = f"Error while retrieving sync run status. Error is: {response.reason}."
                raise FAIL(message=msg)

            return response.json()

    def start_sync_run(self, sync_id: int, wait_for_completion: bool, wait_time_between_api_calls: int, max_wait_time: int) -> Dict:
        """
        TODO
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
                        elapsed_wait_time += wait_time_between_api_calls
                
                msg = "Sync run exceeded `max_wait_time`"
                raise FAIL(message=msg)

            else:
                return start_sync_response
