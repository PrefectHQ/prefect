import pytest
import requests
import responses
import logging

from prefect.tasks.airbyte import (
    AirbyteConnectionTask,
    AirbyteConfigurationExport,
)
from prefect.tasks.airbyte.airbyte import (
    AirbyteServerNotHealthyException,
    ConnectionNotFoundException,
    JobNotFoundException,
)
from prefect.tasks.airbyte.airbyte import AirbyteClient

logging.basicConfig()
log = logging.getLogger()


class TestAirbyte:
    # test airbyte health check
    @responses.activate
    def test_check_health_status(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.GET,
            airbyte_base_url + "/health/",
            json={"db": True},
            status=200,
        )
        airbyte = AirbyteClient(log, airbyte_base_url)
        response = airbyte._establish_session()
        assert response

    @responses.activate
    def test_check_health_status_2(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.GET,
            airbyte_base_url + "/health/",
            json={"db": False},
            status=200,
        )
        airbyte = AirbyteClient(log, airbyte_base_url)
        with pytest.raises(AirbyteServerNotHealthyException):
            airbyte._establish_session()

    @responses.activate
    def test_check_health_status_3(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.GET,
            airbyte_base_url + "/health/",
            json={"available": True},
            status=200,
        )
        airbyte = AirbyteClient(log, airbyte_base_url)
        response = airbyte._establish_session()
        assert response

    @responses.activate
    def test_check_health_status_4(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.GET,
            airbyte_base_url + "/health/",
            json={"available": False},
            status=200,
        )
        airbyte = AirbyteClient(log, airbyte_base_url)
        with pytest.raises(AirbyteServerNotHealthyException):
            airbyte._establish_session()

    # airbyte connection task
    def test_construction(self):
        task = AirbyteConnectionTask()
        assert task.airbyte_server_host == "localhost"
        assert task.airbyte_server_port == 8000

    def test_connection_id_must_be_provided(self):
        task = AirbyteConnectionTask()
        with pytest.raises(ValueError):
            task.run()

    def test_optional_params_are_optional(self):
        task = AirbyteConnectionTask(
            connection_id="749c19dc-4f97-4f30-bb0f-126e53506960"
        )
        try:
            task.run()
        except ValueError as err:
            assert False, str(err)
        except Exception:
            pass

    def test_invalid_connection_id(self):
        task = AirbyteConnectionTask()
        with pytest.raises(ValueError):
            task.run(connection_id="749c19dc-4f97-4f30-bb0f-126e5350696K")

    @responses.activate
    def test_get_connection_status(self):
        """
        Active Connection, No Schedule
        """
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST,
            airbyte_base_url + "/connections/get/",
            json={"status": "active", "schedule": None},
            status=200,
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)
        response = task._get_connection_status(session, airbyte_base_url, connection_id)
        assert response == "active"

    @responses.activate
    def test_get_connection_status_2(self):
        """
        Inactive Connection, No Schedule
        """
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST,
            airbyte_base_url + "/connections/get/",
            json={"status": "inactive", "schedule": None},
            status=200,
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)
        response = task._get_connection_status(session, airbyte_base_url, connection_id)
        assert response == "inactive"

    @responses.activate
    def test_get_connection_status_3(self):
        """
        Deprecated Connection, No Schedule
        """
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST,
            airbyte_base_url + "/connections/get/",
            json={"status": "deprecated", "schedule": None},
            status=200,
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)
        response = task._get_connection_status(session, airbyte_base_url, connection_id)
        assert response == "deprecated"

    @responses.activate
    def test_get_connection_status_4(self):
        """
        Active Connection, Existing Schedule
        """
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST,
            airbyte_base_url + "/connections/get/",
            json={"status": "active", "schedule": {"units": "5"}, "syncCatalog": ""},
            status=200,
        )
        responses.add(
            responses.POST,
            airbyte_base_url + "/connections/update/",
            json={},
            status=200,
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)
        response = task._get_connection_status(session, airbyte_base_url, connection_id)
        assert response == "active"

    @responses.activate
    def test_trigger_manual_sync_connection(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST,
            airbyte_base_url + "/connections/sync/",
            json={"job": {"id": "1", "createdAt": "1234567890"}},
            status=200,
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)
        job_id, job_created_at = task._trigger_manual_sync_connection(
            session, airbyte_base_url, connection_id
        )
        assert job_id == "1"
        assert job_created_at == "1234567890"

    @responses.activate
    def test_trigger_manual_sync_connection_2(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST, airbyte_base_url + "/connections/sync/", json={}, status=404
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)

        with pytest.raises(ConnectionNotFoundException):
            task._trigger_manual_sync_connection(
                session, airbyte_base_url, connection_id
            )

    @responses.activate
    def test_get_job_status(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST,
            airbyte_base_url + "/jobs/get/",
            json={
                "job": {
                    "status": "running",
                    "createdAt": "1234567890",
                    "updatedAt": "1234567890",
                }
            },
            status=200,
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)
        job_id = "1"
        job_status, job_created_at, job_updated_at = task._get_job_status(
            session, airbyte_base_url, job_id
        )
        assert job_status == "running"
        assert job_created_at == "1234567890"
        assert job_updated_at == "1234567890"

    @responses.activate
    def test_get_job_status_2(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.POST, airbyte_base_url + "/jobs/get/", json={}, status=404
        )
        session = requests.Session()
        connection_id = "749c19dc-4f97-4f30-bb0f-126e53506960"
        task = AirbyteConnectionTask(connection_id)

        job_id = "1"
        with pytest.raises(JobNotFoundException):
            task._get_job_status(session, airbyte_base_url, job_id)

    # airbyte export tests
    def test_construction(self):
        task = AirbyteConfigurationExport()
        assert task.airbyte_server_host == "localhost"
        assert task.airbyte_server_port == 8000
        assert task.airbyte_api_version == "v1"

    @responses.activate
    def test_export_configuration(self):
        airbyte_base_url = "http://localhost:8000/api/v1"
        responses.add(
            responses.GET,
            airbyte_base_url + "/health/",
            json={"db": True},
            status=200,
        )
        responses.add(
            responses.POST,
            airbyte_base_url + "/deployment/export/",
            body="\x02\x03\x05\x07",
            status=200,
        )
        task = AirbyteConfigurationExport()
        airbyte_config = task.run()
        assert airbyte_config == b"\x02\x03\x05\x07"
