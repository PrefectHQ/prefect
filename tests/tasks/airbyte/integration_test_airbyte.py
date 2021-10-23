import pytest

from prefect.engine.signals import FAIL
from prefect.tasks.airbyte import AirbyteConnectionTask
from prefect.tasks.airbyte.airbyte import ConnectionNotFoundException


class TestAirbyteIntegration:

    """
    Integration tests for AirbyteConnectionTask

    Please ensure Airbyte Server is running (locally) ...

    """

    # The Connection id to use in integration tests
    CONNECTION_ID = "749c19dc-4f97-4f30-bb0f-126e53506960"

    @pytest.mark.skip(reason="integration test - requires running Airbyte Server ...")
    def test_0(self):
        """
        Ensure Connection with id is created before running ...

        HAPPY PATH: Connection succeeds!

        """
        task = AirbyteConnectionTask(connection_id=self.CONNECTION_ID)
        response = task.run()
        # print(response)
        assert response["connection_id"] == self.CONNECTION_ID
        assert response["status"] == "active"
        assert response["job_status"] == "succeeded"
        assert response["job_updated_at"] > response["job_created_at"]

    @pytest.mark.skip(reason="integration test - requires running Airbyte Server ...")
    def test_1(self):
        """
        Ensure Connection is inactive before running...

        UNHAPPY PATH: Connection inactive

        Returns:

        """
        task = AirbyteConnectionTask(connection_id=self.CONNECTION_ID)
        with pytest.raises(FAIL):
            task.run()

    @pytest.mark.skip(reason="integration test - requires running Airbyte Server ...")
    def test_2(self):
        """
        Ensure Connection is deprecated before running...

        UNHAPPY PATH: Connection deprecated

        Returns:

        """
        task = AirbyteConnectionTask(connection_id=self.CONNECTION_ID)
        with pytest.raises(FAIL):
            task.run()

    @pytest.mark.skip(reason="integration test - requires running Airbyte Server ...")
    def test_3(self):
        """
        UNHAPPY PATH: Connection not found ...
        """
        task = AirbyteConnectionTask(
            connection_id="88888888-4444-4444-4444-CCCCCCCCCCCC"
        )
        with pytest.raises(ConnectionNotFoundException):
            task.run()
