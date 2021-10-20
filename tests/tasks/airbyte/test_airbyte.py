import pytest

from prefect.tasks.airbyte import AirbyteConnectionTask


class TestAirbyte:

    def test_construction(self):
        task = AirbyteConnectionTask()
        assert task.airbyte_server_host == "localhost"
        assert task.airbyte_server_port == 8000

    def test_connection_id_must_be_provided(self):
        task = AirbyteConnectionTask()
        with pytest.raises(ValueError):
            task.run()
