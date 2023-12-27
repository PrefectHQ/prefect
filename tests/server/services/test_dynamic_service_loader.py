import pytest

from prefect.server.services.dynamic_service_loader import string_to_loop_services
from prefect.server.services.loop_service import LoopService


@pytest.mark.parametrize(
    "services_path",
    [
        "prefect.server.services.telemetry.Telemetry",
        "prefect.server.services.late_runs.MarkLateRuns",
        "prefect.server.services.telemetry.Telemetry,prefect.server.services.late_runs.MarkLateRuns",
        (
            " prefect.server.services.telemetry.Telemetry ,"
            " prefect.server.services.late_runs.MarkLateRuns "
        ),
    ],
)
async def test_string_to_loop_services(services_path, session):
    async with session.begin():
        services = string_to_loop_services(services_path)

    for service in services:
        assert isinstance(service, LoopService)
