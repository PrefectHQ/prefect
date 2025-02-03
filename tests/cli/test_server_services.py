from pathlib import Path

import pytest

from prefect import settings
from prefect.server.services.base import Service
from prefect.settings import PREFECT_HOME
from prefect.settings.context import temporary_settings
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def enable_all_services():
    with temporary_settings(
        {
            getattr(settings, enable_service.environment_variable_name()): True
            for enable_service in Service.all_services()
        }
    ):
        yield


@pytest.fixture
def pid_file(monkeypatch: pytest.MonkeyPatch) -> Path:
    pid_file = Path(PREFECT_HOME.value()) / "services.pid"
    monkeypatch.setattr("prefect.cli.server.SERVICES_PID_FILE", pid_file)
    return pid_file


@pytest.fixture(autouse=True)
def cleanup_pid_file(pid_file: Path):
    if pid_file.exists():
        pid_file.unlink()
    yield
    if pid_file.exists():
        pid_file.unlink()


class TestBackgroundServices:
    def test_start_and_stop_services(self, pid_file: Path):
        invoke_and_assert(
            command=[
                "server",
                "services",
                "start",
                "--background",
            ],
            expected_output_contains="Services are running in the background.",
            expected_code=0,
        )

        assert pid_file.exists(), "Services PID file does not exist"

        invoke_and_assert(
            command=[
                "server",
                "services",
                "stop",
            ],
            expected_output_contains="All services stopped.",
            expected_code=0,
        )

        assert not pid_file.exists(), "Services PID file still exists"

    def test_start_duplicate_services(self, pid_file: Path):
        invoke_and_assert(
            command=[
                "server",
                "services",
                "start",
                "--background",
            ],
            expected_output_contains="Services are running in the background.",
            expected_code=0,
        )

        assert pid_file.exists(), "PID file should exist before duplicate test"

        invoke_and_assert(
            command=[
                "server",
                "services",
                "start",
                "--background",
            ],
            expected_output_contains="Services are already running in the background.",
            expected_code=1,
        )

        invoke_and_assert(
            command=[
                "server",
                "services",
                "stop",
            ],
            expected_output_contains="All services stopped.",
            expected_code=0,
        )

    def test_stop_stale_pid_file(self, pid_file: Path):
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("99999")  # Use a likely unused PID

        invoke_and_assert(
            command=[
                "server",
                "services",
                "stop",
            ],
            expected_output_contains="Services were not running",
            expected_output_does_not_contain="All services stopped.",
            expected_code=0,
        )

        assert not pid_file.exists(), "Services PID file still exists"

    def test_list_services(self):
        invoke_and_assert(
            command=[
                "server",
                "services",
                "ls",
            ],
            expected_output_contains=[
                "Available Services",
                "MarkLateRuns",
                "PREFECT_SERVER_SERVICES_LATE_RUNS_ENABLED",
                "Telemetry",
                "PREFECT_SERVER_ANALYTICS_ENABLED",
            ],
            expected_code=0,
        )
