import pytest
import requests
import responses
import logging
import os

from prefect.tasks.fivetran import FivetranSyncTask

logging.basicConfig()
log = logging.getLogger()


class TestFivetran:
    def test_required_params(self):
        """
        Tests to check if there are missing required parameters.
        """

        # raises Value error if connector_id is not provided
        with pytest.raises(
            ValueError, match="Value for parameter `connector_id` must be provided."
        ):
            FivetranSyncTask().run(
                api_key="test",
                api_secret="test",
                schedule_type="auto",
            )

        # raises Value error if api_key is not provided
        with pytest.raises(
            TypeError, match="run() missing 1 required positional argument: 'api_key'"
        ):
            FivetranSyncTask().run(
                connector_id="test",
                api_secret="test",
                schedule_type="auto",
            )
        # raises Value error if api_secret is not provided
        with pytest.raises(
            TypeError,
            match="run() missing 1 required positional argument: 'api_secret'",
        ):
            FivetranSyncTask().run(
                connector_id="test", api_key="test", schedule_type="auto,"
            )
        # raises Value error if schedule_type is not "manual" or "auto"
        with pytest.raises(
            ValueError, match='schedule_type must be either "manual" or "auto"'
        ):
            FivetranSyncTask().run(
                connector_id="test",
                api_key="test",
                api_secret="test",
                schedule_type="test",
            )

    @pytest.mark.skipif(
        os.getenv("FIVETRAN_TEST_API_KEY") is None,
        reason="You need a Fivetran API Key and API Secret to perform an actual Fivetran test",
    )
    def test_fivetran_invalid_endpoint(self) -> None:
        with pytest.raises(
            HTTPError,
            match="404 Client Error: Not Found for url: https://api.fivetran.com/v1/connectors/invalid_id",
        ):
            FivetranSyncTask().run(
                api_key=os.getenv("FIVETRAN_TEST_API_KEY"),
                api_secret=os.getenv("FIVETRAN_TEST_API_SECRET"),
                connector_id="invalid_id",
                schedule_type="auto",
            )

    @pytest.mark.skipif(
        os.getenv("FIVETRAN_TEST_CONNECTOR_ID") is None,
        reason="You need a valid Fivetran connector id to perform this test",
    )
    def test_fivetran_valid_endpoint(self) -> None:
        result = FivetranSyncTask().run(
            api_key=os.getenv("FIVETRAN_TEST_API_KEY"),
            api_secret=os.getenv("FIVETRAN_TEST_API_SECRET"),
            connector_id=os.getenv("FIVETRAN_TEST_CONNECTOR_ID"),
            schedule_type="auto",
        )

        assert isinstance(result, dict)
        
@pytest.fixture
def fivetran_connector_running_response_success():

    response = {
        "code": "Success",
        "data": {
                 "id": "test_connector",
                 "group_id": "test_group',
                 "service": "google_sheets",
                 "service_version": 1,
                 "schema": "test.prefect",
                 "connected_by": "test_user",
                 "created_at": "2021-02-04T18:00:31.027537Z",
                 "succeeded_at": "2022-03-24T01:19:07.208927Z",
                 "failed_at": "2021-12-30T03:06:49.080988Z",
                 "paused": False,
                 "pause_after_trial": False, 
                 "sync_frequency": 1440,
                 "schedule_type": "manual", 
                 "status": {
                     "setup_state": "connected",
                     "schema_status": "ready",
                     "sync_state": "syncing",
                     "update_state": "on_schedule",
                     "is_historical_sync": False,
                     "tasks": [],
                     "warnings": []
                 }, 
                "config": {
                    "sheet_id": "https://docs.google.com/spreadsheets/d/testurl",
                    "named_range": "fivetran_test_range",
                    "authorization_method": "User OAuth",
                    "last_synced_changes__utc_": "2022-03-24 01:18"
                },
        },
    }

    return response

@pytest.fixture
def fivetran_connector_completed_response_success():

    response = {
        "code": "Success",
        "data": {
            "id": "test_connector",
            "group_id": "test_group",
            "service": "google_sheets",
            "service_version": 1,
            "schema": "test.prefect",
            "connected_by": "test_user",
            "created_at": "2021-02-04T18:00:31.027537Z",
            "succeeded_at": "2022-03-25T00:10:59.724443Z",
            "failed_at": "2021-12-30T03:06:49.080988Z",
            "paused": False,
            "pause_after_trial": False,
            "sync_frequency": 1440,
            "schedule_type": "manual",
            "status": {
                "setup_state": "connected",
                "schema_status": "ready", 
                "sync_state": "scheduled", 
                "update_state": "on_schedule",
                "is_historical_sync": False,
                "tasks": [],
                "warnings": []
            },
            "config": {
                "sheet_id": "https://docs.google.com/spreadsheets/d/testurl",
                "named_range": "fivetran_test_range",
                "authorization_method": "User OAuth",
                "last_synced_changes__utc_": "2022-03-25 00:10"
            },
        },
    }
    
    return response
