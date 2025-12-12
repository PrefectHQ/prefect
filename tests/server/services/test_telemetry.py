import json
import platform

import pytest
import respx
from httpx import Response

import prefect
from prefect.server.services.telemetry import (
    _fetch_or_set_telemetry_session,
    send_telemetry_heartbeat,
)


@pytest.fixture
def sens_o_matic_mock():
    with respx.mock(using="httpx") as respx_mock:
        sens_o_matic = respx_mock.post(
            "https://sens-o-matic.prefect.io/",
        ).mock(return_value=Response(200, json={}))

        yield sens_o_matic


@pytest.fixture
def error_sens_o_matic_mock():
    with respx.mock(using="httpx") as respx_mock:
        sens_o_matic = respx_mock.post(
            "https://sens-o-matic.prefect.io/",
        ).mock(return_value=Response(500, json={}))

        yield sens_o_matic


async def test_sens_o_matic_called_correctly(sens_o_matic_mock):
    from prefect.client.constants import SERVER_API_VERSION

    await send_telemetry_heartbeat()

    assert sens_o_matic_mock.called
    assert sens_o_matic_mock.call_count == 1

    request = sens_o_matic_mock.calls[0].request
    assert request.headers["x-prefect-event"] == "prefect_server"

    heartbeat = json.loads(request.content.decode("utf-8"))
    assert heartbeat["type"] == "heartbeat"
    assert heartbeat["source"] == "prefect_server"

    payload = heartbeat["payload"]
    assert payload["platform"] == platform.system()
    assert payload["architecture"] == platform.machine()
    assert payload["python_version"] == platform.python_version()
    assert payload["python_implementation"] == platform.python_implementation()

    assert payload["api_version"] == SERVER_API_VERSION
    assert payload["prefect_version"] == prefect.__version__

    # Session info should be present
    assert payload["session_id"]
    assert payload["session_start_timestamp"]


async def test_sets_and_fetches_session_information():
    from prefect.server.database import provide_database_interface

    db = provide_database_interface()

    # Get session info from first call
    session_start_timestamp_1, session_id_1 = await _fetch_or_set_telemetry_session(
        db=db
    )
    assert session_id_1
    assert session_start_timestamp_1

    # Retrieve from the db if process restarted (same session info)
    session_start_timestamp_2, session_id_2 = await _fetch_or_set_telemetry_session(
        db=db
    )
    assert session_id_2 == session_id_1
    assert session_start_timestamp_2 == session_start_timestamp_1


async def test_errors_do_not_crash_service(error_sens_o_matic_mock, caplog):
    # When telemetry encounters an error, it logs but doesn't crash
    await send_telemetry_heartbeat()

    assert error_sens_o_matic_mock.called
    assert error_sens_o_matic_mock.call_count == 1

    # Filter for telemetry error logs
    records = [
        record
        for record in caplog.records
        if record.name == "prefect.server.services.telemetry"
        and record.levelname == "ERROR"
    ]

    assert len(records) == 1, "An error level log should be emitted"
    assert "Failed to send telemetry" in records[0].message, (
        "Should inform the user of the failure"
    )

    assert "Server error '500 Internal Server Error' for url" in records[0].message, (
        "Should include a short version of the exception"
    )
