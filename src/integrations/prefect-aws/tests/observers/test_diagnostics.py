"""Tests for prefect_aws.observers.diagnostics."""

import logging

import pytest
from prefect_aws.observers.diagnostics import (
    InfrastructureDiagnosis,
    diagnose_ecs_task,
)


class TestDiagnoseEcsTask:
    """Tests for diagnose_ecs_task."""

    def test_non_stopped_task_returns_none(self):
        detail = {"lastStatus": "RUNNING", "containers": []}
        assert diagnose_ecs_task(detail) is None

    def test_missing_last_status_returns_none(self):
        assert diagnose_ecs_task({}) is None

    def test_stopped_task_with_all_zero_exits_returns_none(self):
        detail = {
            "lastStatus": "STOPPED",
            "stopCode": "",
            "stoppedReason": "",
            "containers": [{"name": "app", "exitCode": 0}],
        }
        assert diagnose_ecs_task(detail) is None

    def test_null_stopped_reason_does_not_raise(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": None,
            "stopCode": None,
            "containers": [{"name": "app", "exitCode": 1}],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.summary == "Container exited with non-zero exit code"

    # --- CannotPullContainerError ---

    def test_cannot_pull_container_error(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": ("CannotPullContainerError: ref pull has been retried"),
            "stopCode": "TaskFailedToStart",
            "containers": [],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.level == logging.ERROR
        assert result.summary == "Container image pull failed"
        assert "CannotPullContainerError" in result.detail
        assert "image" in result.resolution.lower()

    # --- TaskFailedToStart ---

    def test_task_failed_to_start(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "Timeout waiting for network interface provisioning to complete.",
            "stopCode": "TaskFailedToStart",
            "containers": [],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.level == logging.ERROR
        assert result.summary == "ECS task failed to start"
        assert "Timeout" in result.detail

    def test_task_failed_to_start_no_reason(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "",
            "stopCode": "TaskFailedToStart",
            "containers": [],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.summary == "ECS task failed to start"
        assert "no additional detail" in result.detail.lower()

    # --- EssentialContainerExited ---

    def test_essential_container_exited_with_nonzero_code(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "Essential container in task exited",
            "stopCode": "EssentialContainerExited",
            "containers": [
                {"name": "app", "exitCode": 1},
                {"name": "sidecar", "exitCode": 0},
            ],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.level == logging.ERROR
        assert result.summary == "Essential container exited"
        assert "app" in result.detail
        assert "code 1" in result.detail

    def test_essential_container_exited_with_null_exit_code(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "Essential container in task exited",
            "stopCode": "EssentialContainerExited",
            "containers": [
                {"name": "app", "exitCode": None},
            ],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.summary == "Essential container exited"
        assert "no exit code" in result.detail.lower()

    # --- Non-zero exit codes ---

    def test_container_nonzero_exit_code(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "",
            "stopCode": "ServiceSchedulerInitiated",
            "containers": [
                {"name": "web", "exitCode": 137},
            ],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.level == logging.ERROR
        assert result.summary == "Container exited with non-zero exit code"
        assert "137" in result.detail

    def test_multiple_container_failures(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "",
            "stopCode": "",
            "containers": [
                {"name": "app", "exitCode": 1},
                {"name": "sidecar", "exitCode": 2},
            ],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert "app" in result.detail
        assert "sidecar" in result.detail

    # --- Null exit code (infrastructure kill) ---

    def test_null_exit_code_infrastructure_kill(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "",
            "stopCode": "",
            "containers": [
                {"name": "app", "exitCode": None},
            ],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.level == logging.WARNING
        assert result.summary == "Task terminated by infrastructure"
        assert "no exit code" in result.detail.lower()

    def test_mixed_null_and_nonzero_exit_codes(self):
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "",
            "stopCode": "",
            "containers": [
                {"name": "app", "exitCode": 1},
                {"name": "monitor", "exitCode": None},
            ],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.level == logging.ERROR
        assert "app" in result.detail
        assert "monitor" in result.detail

    # --- CannotPullContainerError takes priority over stopCode ---

    def test_cannot_pull_takes_priority_over_stop_code(self):
        """CannotPullContainerError in stoppedReason is checked before stopCode."""
        detail = {
            "lastStatus": "STOPPED",
            "stoppedReason": "CannotPullContainerError: image not found",
            "stopCode": "EssentialContainerExited",
            "containers": [{"name": "app", "exitCode": 1}],
        }
        result = diagnose_ecs_task(detail)
        assert result is not None
        assert result.summary == "Container image pull failed"

    # --- Return type ---

    def test_returns_frozen_dataclass(self):
        detail = {
            "lastStatus": "STOPPED",
            "stopCode": "TaskFailedToStart",
            "containers": [],
        }
        result = diagnose_ecs_task(detail)
        assert isinstance(result, InfrastructureDiagnosis)
        with pytest.raises(AttributeError):
            result.summary = "modified"  # type: ignore[misc]
