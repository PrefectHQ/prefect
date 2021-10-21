import pytest

from prefect.tasks.airbyte import AirbyteConnectionTask
from prefect.tasks.airbyte.airbyte import AirbyteServerNotHealthyException


class TestAirbyte:

    def test_construction(self):
        task = AirbyteConnectionTask()
        assert task.airbyte_server_host == "localhost"
        assert task.airbyte_server_port == 8000

    def test_connection_id_must_be_provided(self):
        task = AirbyteConnectionTask()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_connection_id(self):
        task = AirbyteConnectionTask()
        with pytest.raises(ValueError):
            task.run(connection_id="749c19dc-4f97-4f30-bb0f-126e5350696K")

    def test_no_airbyte_server(self):
        task = AirbyteConnectionTask()
        with pytest.raises(AirbyteServerNotHealthyException):
            task.run(connection_id="749c19dc-4f97-4f30-bb0f-126e53506960")

