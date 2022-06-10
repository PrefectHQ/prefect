import json
import platform

import pytest
import respx
from httpx import Response

import prefect
from prefect.orion.services.telemetry import Telemetry


@pytest.fixture
def sens_o_matic_mock():
    with respx.mock:
        sens_o_matic = respx.post(
            "https://sens-o-matic.prefect.io/",
        ).mock(return_value=Response(200, json={}))

        yield sens_o_matic


async def test_sens_o_matic_called_correctly(sens_o_matic_mock):
    from prefect.orion.api.server import ORION_API_VERSION

    telemetry = Telemetry()
    await telemetry.start(loops=1)

    assert sens_o_matic_mock.called
    assert sens_o_matic_mock.call_count == 1

    request = sens_o_matic_mock.calls[0].request
    assert request.headers["x-prefect-event"] == "prefect_server"

    heartbeat = json.loads(request.content.decode("utf-8"))
    assert heartbeat["type"] == "orion_heartbeat"
    assert heartbeat["source"] == "prefect_server"

    payload = heartbeat["payload"]
    assert payload["platform"] == platform.system()
    assert payload["architecture"] == platform.machine()
    assert payload["python_version"] == platform.python_version()
    assert payload["python_implementation"] == platform.python_implementation()

    assert payload["api_version"] == ORION_API_VERSION
    assert payload["prefect_version"] == prefect.__version__

    assert payload["session_id"] == telemetry.session_id
    assert payload["session_start_timestamp"] == telemetry.session_start_timestamp


async def test_sets_and_fetches_session_information(sens_o_matic_mock):
    telemetry = Telemetry()
    await telemetry.start(loops=1)

    # set it on the first call
    sid = telemetry.session_id
    sts = telemetry.session_start_timestamp
    assert sid
    assert sts

    # retrieve from the db if process restarted
    telemetry_2 = Telemetry()
    await telemetry_2.start(loops=1)
    assert telemetry_2.session_id == sid
    assert telemetry_2.session_start_timestamp == sts
