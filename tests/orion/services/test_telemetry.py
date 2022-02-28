import ast

import pytest
import respx
from httpx import Response

import prefect
from prefect.orion import models, schemas
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
    request.headers["x-prefect-event"] == "prefect_server"

    request_content = ast.literal_eval(request.content.decode("utf-8"))
    request_content["type"] == "orion_heartbeat"
    request_content["source"] == "prefect_server"
    request_content["source"] == "prefect_server"

    request_payload = request_content["payload"]
    request_payload["api_version"] == ORION_API_VERSION
    request_payload["prefect_version"] == prefect.__version__
    request_payload["session_id"] == telemetry.session_id
    request_payload["session_start_timestamp"] == telemetry.session_start_timestamp


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
