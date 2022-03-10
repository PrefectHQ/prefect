import pytest
import requests
import responses
import logging

from prefect.task.fivetran import FivetranSyncTask

logging.basicConfig()
log = logging.getLogger()

class TestFivetran:
    def test_required_params(self):
        """
        Tests to check if there are missing required parameters.
        """

        # raises Value error if connector_id is not provided
        with pytest.raises(ValueError, match="Value for parameter `connector_id` must be provided."):
            FivetranSyncTask().run(
                api_key="test",
                api_secret="test",
                schedule_type="auto",
            )

        # raises Value error if api_key is not provided
        with pytest.raises(ValueError, match="Value for parameter `api_key` must be provided."):
            FivetranSyncTask().run(
                connector_id="test",
                api_secret="test",
                schedule_type="auto",
            )
        # raises Value error if api_secret is not provided
        with pytest.raises(ValueError, match="Value for parameter `api_secret` must be provided."):
            FivetranSyncTask().run(
                connector_id="test",
                api_key="test",
                schedule_type="auto,"
            ) 
        # raises Value error if schedule_type is not "manual" or "auto"
        with pytest.raises(ValueError, match='schedule_type must be either "manual" or "auto"'):
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
