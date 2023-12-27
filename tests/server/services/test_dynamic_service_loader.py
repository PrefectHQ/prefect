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
    async with session:
        services = string_to_loop_services(services_path)

    assert len(services) == len(services_path.split(","))
    for service in services:
        assert isinstance(service, LoopService)


@pytest.mark.parametrize(
    ["services_path", "nb_result_services"],
    [
        ("prefect.server.services.telemetry.Telemetry", 1),
        ("prefect.server.services.late_runs.MarkLateRuns", 1),
        (
            "prefect.server.services.telemetry.Telemetry,prefect.server.services.late_runs.MarkLateRuns",
            2,
        ),
        (
            (
                " prefect.server.services.telemetry.Telemetry ,"
                " prefect.server.services.late_runs.MarkLateRuns "
            ),
            2,
        ),
        (
            "prefect.server.services.telemetry.Telemetry,prefect.server.services.late_runs.someService",
            1,
        ),
        ("prefect.server.services.telemetry.Telemetry,prefect.tasks.Task", 1),
    ],
)
async def test_return_only_valid_service_loop(
    services_path: str, nb_result_services: int, session
):
    async with session.begin():
        services = string_to_loop_services(services_path)

    assert len(services) == nb_result_services
    for service in services:
        assert isinstance(service, LoopService)
