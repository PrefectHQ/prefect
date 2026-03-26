"""Tests for prefect_kubernetes.diagnostics."""

import pytest
from prefect_kubernetes.diagnostics import (
    DiagnosisLevel,
    InfrastructureDiagnosis,
    diagnose_k8s_pod,
)


class TestDiagnoseKubernetesPod:
    """Tests for diagnose_k8s_pod."""

    # --- Happy path: no diagnosis -----------------------------------------

    def test_healthy_running_pod_returns_none(self):
        status = {
            "phase": "Running",
            "containerStatuses": [
                {
                    "name": "main",
                    "state": {"running": {"startedAt": "2024-01-01T00:00:00Z"}},
                }
            ],
        }
        assert diagnose_k8s_pod(status) is None

    def test_empty_status_returns_none(self):
        assert diagnose_k8s_pod({}) is None

    def test_no_container_statuses_returns_none(self):
        status = {"phase": "Pending"}
        assert diagnose_k8s_pod(status) is None

    def test_succeeded_pod_returns_none(self):
        status = {
            "phase": "Succeeded",
            "containerStatuses": [
                {
                    "name": "main",
                    "state": {"terminated": {"exitCode": 0, "reason": "Completed"}},
                }
            ],
        }
        assert diagnose_k8s_pod(status) is None

    # --- ImagePullBackOff / ErrImagePull ----------------------------------

    @pytest.mark.parametrize("reason", ["ImagePullBackOff", "ErrImagePull"])
    def test_image_pull_failure(self, reason: str):
        status = {
            "containerStatuses": [
                {
                    "name": "flow-run",
                    "state": {
                        "waiting": {
                            "reason": reason,
                            "message": 'rpc error: pull access denied for "myimage"',
                        }
                    },
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.ERROR
        assert "flow-run" in result.summary
        assert reason in result.detail
        assert "image" in result.resolution.lower()

    def test_image_pull_failure_without_message(self):
        status = {
            "containerStatuses": [
                {
                    "name": "flow-run",
                    "state": {"waiting": {"reason": "ImagePullBackOff"}},
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.ERROR

    # --- OOMKilled --------------------------------------------------------

    def test_oom_killed(self):
        status = {
            "containerStatuses": [
                {
                    "name": "worker",
                    "state": {
                        "terminated": {
                            "reason": "OOMKilled",
                            "exitCode": 137,
                        }
                    },
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.ERROR
        assert "OOMKilled" in result.summary
        assert "worker" in result.summary
        assert "memory" in result.resolution.lower()

    # --- CrashLoopBackOff -------------------------------------------------

    def test_crash_loop_backoff(self):
        status = {
            "containerStatuses": [
                {
                    "name": "main",
                    "state": {
                        "waiting": {
                            "reason": "CrashLoopBackOff",
                            "message": "back-off 5m0s restarting failed container",
                        }
                    },
                    "restartCount": 5,
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.ERROR
        assert "crash-looping" in result.summary
        assert "logs" in result.resolution.lower()

    # --- Unschedulable ----------------------------------------------------

    def test_unschedulable(self):
        status = {
            "conditions": [
                {
                    "type": "PodScheduled",
                    "status": "False",
                    "reason": "Unschedulable",
                    "message": "0/3 nodes are available: insufficient cpu.",
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.WARNING
        assert "unschedulable" in result.summary.lower()
        assert "insufficient cpu" in result.detail

    def test_unschedulable_without_message(self):
        status = {
            "conditions": [
                {
                    "type": "PodScheduled",
                    "status": "False",
                    "reason": "Unschedulable",
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.WARNING

    def test_scheduled_condition_is_not_flagged(self):
        """A PodScheduled condition that is not Unschedulable should be ignored."""
        status = {
            "conditions": [
                {
                    "type": "PodScheduled",
                    "status": "True",
                    "reason": "Scheduled",
                }
            ],
        }
        assert diagnose_k8s_pod(status) is None

    # --- Evicted (pod-level) ----------------------------------------------

    def test_evicted_pod_level(self):
        status = {
            "phase": "Failed",
            "reason": "Evicted",
            "message": "The node was low on resource: memory.",
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.WARNING
        assert "evicted" in result.summary.lower()
        assert "memory" in result.detail.lower()

    def test_evicted_pod_level_without_message(self):
        status = {
            "phase": "Failed",
            "reason": "Evicted",
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.WARNING

    # --- Evicted (container-level) ----------------------------------------

    def test_evicted_container_level(self):
        status = {
            "containerStatuses": [
                {
                    "name": "main",
                    "state": {
                        "terminated": {
                            "reason": "Evicted",
                            "exitCode": 137,
                        }
                    },
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.level == DiagnosisLevel.WARNING
        assert "evicted" in result.summary.lower()

    # --- Init container failures ------------------------------------------

    def test_init_container_image_pull_failure(self):
        status = {
            "initContainerStatuses": [
                {
                    "name": "init-setup",
                    "state": {
                        "waiting": {
                            "reason": "ImagePullBackOff",
                            "message": "Back-off pulling image",
                        }
                    },
                }
            ],
            "containerStatuses": [
                {
                    "name": "main",
                    "state": {"waiting": {"reason": "PodInitializing"}},
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert "init-setup" in result.summary

    def test_init_container_oom_killed(self):
        status = {
            "initContainerStatuses": [
                {
                    "name": "data-loader",
                    "state": {
                        "terminated": {
                            "reason": "OOMKilled",
                            "exitCode": 137,
                        }
                    },
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert "OOMKilled" in result.summary
        assert "data-loader" in result.summary

    # --- Priority: first failure wins -------------------------------------

    def test_waiting_failure_takes_priority_over_terminated(self):
        """If a container has both a waiting and terminated failure, waiting wins."""
        status = {
            "containerStatuses": [
                {
                    "name": "a",
                    "state": {
                        "waiting": {"reason": "CrashLoopBackOff"},
                    },
                },
                {
                    "name": "b",
                    "state": {
                        "terminated": {"reason": "OOMKilled", "exitCode": 137},
                    },
                },
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert "crash-looping" in result.summary

    # --- InfrastructureDiagnosis dataclass --------------------------------

    def test_diagnosis_is_frozen(self):
        d = InfrastructureDiagnosis(
            level=DiagnosisLevel.ERROR,
            summary="test",
            detail="test",
            resolution="test",
        )
        with pytest.raises(AttributeError):
            d.summary = "changed"  # type: ignore[misc]

    def test_diagnosis_equality(self):
        a = InfrastructureDiagnosis(
            level=DiagnosisLevel.ERROR,
            summary="s",
            detail="d",
            resolution="r",
        )
        b = InfrastructureDiagnosis(
            level=DiagnosisLevel.ERROR,
            summary="s",
            detail="d",
            resolution="r",
        )
        assert a == b
