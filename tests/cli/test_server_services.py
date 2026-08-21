import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from prefect import settings
from prefect.server.services.base import Service
from prefect.settings import PREFECT_HOME
from prefect.settings.context import temporary_settings
from prefect.testing.cli import invoke_and_assert

pytestmark = pytest.mark.clear_db


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
    monkeypatch.setattr("prefect.cli._server_utils.SERVICES_PID_FILE", pid_file)
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
                "TaskRunRecorder",
                # May be truncated in table display
                "PREFECT_SERVER_SERVICES_TASK_RUN_RECORDER",
                "Scheduler",
                "Late Runs",
                # May be truncated in table display
                "Cancellation Clean",
                "Pause Expirations",
                "Repossessor",
                "Cleanup Reconciler",
                "Foreman",
                "DB Vacuum",
                "Proactive Triggers",
                "Telemetry",
            ],
            expected_code=0,
        )

    def test_list_services_json_output(self):
        result = invoke_and_assert(
            command=[
                "server",
                "services",
                "ls",
                "--output",
                "json",
            ],
            expected_code=0,
        )

        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert payload, "Expected non-empty JSON list"

        required_keys = {"name", "enabled", "environment_variable", "description"}
        for item in payload:
            assert required_keys.issubset(item.keys())

    def test_list_services_json_output_short_flag(self):
        result = invoke_and_assert(
            command=[
                "server",
                "services",
                "ls",
                "-o",
                "json",
            ],
            expected_code=0,
        )

        payload = json.loads(result.stdout)
        assert isinstance(payload, list)

    def test_list_services_invalid_output_format(self):
        invoke_and_assert(
            command=[
                "server",
                "services",
                "ls",
                "--output",
                "xml",
            ],
            expected_code=1,
            expected_output_contains="Only 'json' output format is supported.",
        )


CLASS_SERVICE_DISABLE_UPDATES: dict[str, bool] = {
    "PREFECT_SERVER_SERVICES_TASK_RUN_RECORDER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_EVENT_LOGGER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": False,
    "PREFECT_SERVER_EVENTS_STREAM_OUT_ENABLED": False,
    "PREFECT_SERVER_LOGS_STREAM_OUT_ENABLED": False,
}

PERPETUAL_SERVICE_DISABLE_UPDATES: dict[str, bool | None] = {
    "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_LATE_RUNS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_CANCELLATION_CLEANUP_ENABLED": False,
    "PREFECT_SERVER_SERVICES_PAUSE_EXPIRATIONS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_REPOSSESSOR_ENABLED": False,
    "PREFECT_SERVER_SERVICES_CLEANUP_RECONCILER_ENABLED": False,
    "PREFECT_SERVER_SERVICES_FOREMAN_ENABLED": False,
    "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": None,
    "PREFECT_SERVER_ANALYTICS_ENABLED": False,
    "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED": False,
}

EXPECTED_SERVICE_LS_ORDER: list[str] = [
    "TaskRunRecorder",
    "EventLogger",
    "EventPersister",
    "ReactiveTriggers",
    "Actions",
    "Distributor",
    "LogDistributor",
    "Scheduler",
    "Late Runs",
    "Cancellation Cleanup",
    "Pause Expirations",
    "Repossessor",
    "Cleanup Reconciler",
    "Foreman",
    "DB Vacuum",
    "Proactive Triggers",
    "Telemetry",
]


class TestBackgroundServiceInventory:
    def test_list_services_json_is_deterministic_and_keeps_required_fields(self):
        first = invoke_and_assert(
            command=["server", "services", "ls", "--output", "json"],
            expected_code=0,
        )
        second = invoke_and_assert(
            command=["server", "services", "ls", "--output", "json"],
            expected_code=0,
        )
        assert first.stdout == second.stdout

        payload = json.loads(first.stdout)
        required_keys = {"name", "enabled", "environment_variable", "description"}
        for item in payload:
            assert required_keys.issubset(item.keys())

        assert [item["name"] for item in payload] == EXPECTED_SERVICE_LS_ORDER

    def test_list_services_json_reports_canonical_distributor_env_var(self):
        result = invoke_and_assert(
            command=["server", "services", "ls", "--output", "json"],
            expected_code=0,
        )
        payload = json.loads(result.stdout)
        distributor = next(item for item in payload if item["name"] == "Distributor")
        assert (
            distributor["environment_variable"]
            == "PREFECT_SERVER_EVENTS_STREAM_OUT_ENABLED"
        )
        assert "PREFECT_API_EVENTS_STREAM_OUT_ENABLED" not in json.dumps(payload)

    def test_list_services_json_reports_shared_controls(self):
        result = invoke_and_assert(
            command=["server", "services", "ls", "--output", "json"],
            expected_code=0,
        )
        payload = json.loads(result.stdout)
        by_name = {item["name"]: item for item in payload}

        scheduler = by_name["Scheduler"]
        assert scheduler["shared_control"] is True
        assert scheduler["components"] == [
            "schedule_deployments",
            "schedule_recent_deployments",
        ]
        assert (
            scheduler["environment_variable"]
            == "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED"
        )

        cancellation = by_name["Cancellation Cleanup"]
        assert cancellation["shared_control"] is True
        assert cancellation["components"] == [
            "ensure_cancelling_timeout_checks",
            "monitor_cancelled_flow_runs",
            "monitor_subflow_runs",
        ]

        for name in ("ReactiveTriggers", "Actions", "Proactive Triggers"):
            item = by_name[name]
            assert item["shared_control"] is True
            assert (
                item["environment_variable"]
                == "PREFECT_SERVER_SERVICES_TRIGGERS_ENABLED"
            )
            assert item["components"] == [
                "ReactiveTriggers",
                "Actions",
                "evaluate_proactive_triggers_periodic",
            ]

        vacuum = by_name["DB Vacuum"]
        assert vacuum["shared_control"] is True
        assert vacuum["components"] == ["events", "flow_runs"]
        assert "component_state" in vacuum

        telemetry = by_name["Telemetry"]
        assert telemetry["environment_variable"] == "PREFECT_SERVER_ANALYTICS_ENABLED"

    def test_class_only_configuration_starts(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("prefect.cli._server_utils._run_all_services", AsyncMock())
        with temporary_settings(
            {
                **PERPETUAL_SERVICE_DISABLE_UPDATES,
                **CLASS_SERVICE_DISABLE_UPDATES,
                "PREFECT_SERVER_SERVICES_TASK_RUN_RECORDER_ENABLED": True,
            }
        ):
            invoke_and_assert(
                command=["server", "services", "start"],
                expected_code=0,
                expected_output_contains="Starting services",
                expected_output_does_not_contain="No services are enabled!",
            )

    def test_perpetual_only_configuration_passes_preflight(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr("prefect.cli._server_utils._run_all_services", AsyncMock())
        with temporary_settings(
            {
                **CLASS_SERVICE_DISABLE_UPDATES,
                **PERPETUAL_SERVICE_DISABLE_UPDATES,
                "PREFECT_SERVER_SERVICES_SCHEDULER_ENABLED": True,
            }
        ):
            invoke_and_assert(
                command=["server", "services", "start"],
                expected_code=0,
                expected_output_contains="Starting services",
                expected_output_does_not_contain="No services are enabled!",
            )
            invoke_and_assert(
                command=["server", "services", "manager"],
                expected_code=0,
                expected_output_does_not_contain="No services are enabled!",
            )

    def test_empty_service_configuration_fails(self):
        with temporary_settings(
            {**CLASS_SERVICE_DISABLE_UPDATES, **PERPETUAL_SERVICE_DISABLE_UPDATES}
        ):
            invoke_and_assert(
                command=["server", "services", "start"],
                expected_code=1,
                expected_output_contains="No services are enabled!",
            )
            invoke_and_assert(
                command=["server", "services", "manager"],
                expected_code=1,
            )

    def test_foreground_and_manager_use_shared_eligibility_helper(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        sentinel = MagicMock(return_value=False)
        monkeypatch.setattr(
            "prefect.server.services._inventory._has_enabled_background_services",
            sentinel,
        )
        invoke_and_assert(
            command=["server", "services", "start"],
            expected_code=1,
            expected_output_contains="No services are enabled!",
        )
        invoke_and_assert(
            command=["server", "services", "manager"],
            expected_code=1,
        )
        assert sentinel.call_count == 2

    def test_list_services_text_shows_db_vacuum_component_states(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        import prefect.cli._app as cli_app

        original_console = cli_app.Console

        def wide_console(*args: object, **kwargs: object):
            # Rich treats non-TTY StringIO as a dumb terminal and ignores
            # width unless height is also set (early-return in Console.size).
            kwargs["width"] = 200
            kwargs["height"] = 50
            return original_console(*args, **kwargs)

        monkeypatch.setattr(cli_app, "Console", wide_console)

        with temporary_settings(
            {
                "PREFECT_SERVER_SERVICES_EVENT_PERSISTER_ENABLED": True,
                "PREFECT_SERVER_SERVICES_DB_VACUUM_ENABLED": "events",
            }
        ):
            json_result = invoke_and_assert(
                command=["server", "services", "ls", "--output", "json"],
                expected_code=0,
            )
            payload = json.loads(json_result.stdout)
            vacuum = next(item for item in payload if item["name"] == "DB Vacuum")
            assert vacuum["shared_control"] is True
            assert vacuum["components"] == ["events", "flow_runs"]
            assert vacuum["component_state"] == {
                "events": True,
                "flow_runs": False,
            }

            invoke_and_assert(
                command=["server", "services", "ls"],
                expected_code=0,
                expected_output_contains=[
                    "DB Vacuum",
                    "events=enabled",
                    "flow_runs=disabled",
                ],
            )
