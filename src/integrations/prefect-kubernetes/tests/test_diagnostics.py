"""Tests for prefect_kubernetes.diagnostics."""

import pytest
from prefect_kubernetes.diagnostics import (
    DiagnosisCategory,
    DiagnosisLevel,
    InfrastructureDiagnosis,
    diagnose_k8s_pod,
)


def _unschedulable_diagnosis(message: str) -> InfrastructureDiagnosis:
    diagnosis = diagnose_k8s_pod(
        {
            "conditions": [
                {
                    "type": "PodScheduled",
                    "reason": "Unschedulable",
                    "message": message,
                }
            ]
        }
    )
    assert diagnosis is not None
    return diagnosis


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
        assert result.category == DiagnosisCategory.IMAGE_PULL_ERROR
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
        assert result.category == DiagnosisCategory.OOM_KILLED
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
        assert result.category == DiagnosisCategory.CRASH_LOOP_BACKOFF
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
        assert result.category == DiagnosisCategory.UNSCHEDULABLE_INSUFFICIENT_RESOURCES
        assert "unschedulable" in result.summary.lower()
        assert "insufficient cpu" in result.detail

    @pytest.mark.parametrize(
        "message,expected_category",
        [
            (
                "0/3 nodes are available: 3 insufficient memory.",
                DiagnosisCategory.UNSCHEDULABLE_INSUFFICIENT_RESOURCES,
            ),
            (
                "0/3 nodes are available: 3 node(s) didn't match Pod's node affinity/selector.",
                DiagnosisCategory.UNSCHEDULABLE_NODE_AFFINITY,
            ),
            (
                "0/3 nodes are available: 3 node(s) had untolerated taint {key: value}.",
                DiagnosisCategory.UNSCHEDULABLE_TAINT,
            ),
            (
                "0/3 nodes are available: 3 node(s) had volume node affinity conflict.",
                DiagnosisCategory.UNSCHEDULABLE_NODE_AFFINITY,
            ),
            (
                "0/3 nodes are available: 3 node(s) didn't match pod topology spread constraints.",
                DiagnosisCategory.UNSCHEDULABLE,
            ),
            (
                "0/3 nodes are available for some unknown reason.",
                DiagnosisCategory.UNSCHEDULABLE,
            ),
        ],
    )
    def test_unschedulable_categorized_by_cause(
        self, message: str, expected_category: DiagnosisCategory
    ):
        status = {
            "conditions": [
                {
                    "type": "PodScheduled",
                    "status": "False",
                    "reason": "Unschedulable",
                    "message": message,
                }
            ],
        }
        result = diagnose_k8s_pod(status)
        assert result is not None
        assert result.category == expected_category

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
        assert result.category == DiagnosisCategory.UNSCHEDULABLE

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
        assert result.category == DiagnosisCategory.EVICTED
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
        assert result.category == DiagnosisCategory.EVICTED
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
            category=DiagnosisCategory.OOM_KILLED,
            summary="test",
            detail="test",
            resolution="test",
        )
        with pytest.raises(AttributeError):
            d.summary = "changed"  # type: ignore[misc]

    def test_diagnosis_equality(self):
        a = InfrastructureDiagnosis(
            level=DiagnosisLevel.ERROR,
            category=DiagnosisCategory.OOM_KILLED,
            summary="s",
            detail="d",
            resolution="r",
        )
        b = InfrastructureDiagnosis(
            level=DiagnosisLevel.ERROR,
            category=DiagnosisCategory.OOM_KILLED,
            summary="s",
            detail="d",
            resolution="r",
        )
        assert a == b

    # --- dedupe_key --------------------------------------------------------

    def test_dedupe_key_distinguishes_categories(self):
        unschedulable = _unschedulable_diagnosis(
            "0/3 nodes are available: 3 node(s) had untolerated taint."
        )
        oom = diagnose_k8s_pod(
            {
                "containerStatuses": [
                    {
                        "name": "main",
                        "state": {"terminated": {"reason": "OOMKilled"}},
                    }
                ]
            }
        )
        assert oom is not None
        assert unschedulable._dedupe_key() != oom._dedupe_key()

    def test_dedupe_key_distinguishes_oom_killed_containers(self):
        worker_one = diagnose_k8s_pod(
            {
                "containerStatuses": [
                    {
                        "name": "worker-1",
                        "state": {"terminated": {"reason": "OOMKilled"}},
                    }
                ]
            }
        )
        worker_two = diagnose_k8s_pod(
            {
                "containerStatuses": [
                    {
                        "name": "worker-2",
                        "state": {"terminated": {"reason": "OOMKilled"}},
                    }
                ]
            }
        )
        assert worker_one is not None and worker_two is not None
        assert worker_one._dedupe_key() != worker_two._dedupe_key()

    @pytest.mark.parametrize(
        ("first_detail", "second_detail"),
        [
            (
                "0/3 nodes are available: 3 Insufficient cpu.",
                "0/5 nodes are available: 5 Insufficient cpu.",
            ),
            (
                "0/3 nodes are available: 2 Insufficient cpu, 1 Insufficient memory.",
                "0/4 nodes are available: 1 Insufficient memory, 3 Insufficient cpu.",
            ),
            (
                (
                    "0/8 nodes are available: 8 Insufficient cpu, "
                    "2 node(s) had untolerated taint. preemption: "
                    "0/8 nodes are available: 8 Preemption is not helpful for "
                    "scheduling, 2 No preemption victims found for incoming pod."
                ),
                (
                    "0/12 nodes are available: 4 node(s) had untolerated taint, "
                    "12 Insufficient cpu. preemption: 0/15 nodes are available: "
                    "3 No preemption victims found for incoming pod, 12 Preemption "
                    "is not helpful for scheduling."
                ),
            ),
            (
                (
                    "0/1 nodes are available: preemption: 0/1 nodes are available: "
                    "1 Preemption is not helpful for scheduling."
                ),
                (
                    "0/2 nodes are available: preemption: 0/2 nodes are available: "
                    "2 Preemption is not helpful for scheduling."
                ),
            ),
            (
                (
                    "0/1 nodes are available: 1 cannot allocate all claims. "
                    "still not schedulable, preemption: 0/1 nodes are available: "
                    "1 Preemption is not helpful for scheduling."
                ),
                (
                    "0/2 nodes are available: 2 cannot allocate all claims. "
                    "still not schedulable, preemption: 0/2 nodes are available: "
                    "2 Preemption is not helpful for scheduling."
                ),
            ),
            (
                (
                    "0/3 nodes are available: Node(s) failed PreFilter plugin "
                    "FalsePreFilter. preemption: 0/3 nodes are available: "
                    "3 Preemption is not helpful for scheduling."
                ),
                (
                    "0/5 nodes are available: Node(s) failed PreFilter plugin "
                    "FalsePreFilter. preemption: 0/5 nodes are available: "
                    "5 Preemption is not helpful for scheduling."
                ),
            ),
            (
                (
                    "0/3 nodes are available: 3 node(s) had untolerated taint "
                    "{node-role.kubernetes.io/master: }."
                ),
                (
                    "0/8 nodes are available: 8 node(s) had untolerated taint "
                    "{node-role.kubernetes.io/master: }."
                ),
            ),
            (
                (
                    "0/3 nodes are available: 3 node(s) didn't match Pod's node "
                    "affinity/selector."
                ),
                (
                    "0/5 nodes are available: 5 node(s) didn't match Pod's node "
                    "affinity/selector."
                ),
            ),
            (
                (
                    "0/3 nodes are available: 3 node(s) had volume node affinity "
                    "conflict."
                ),
                (
                    "0/5 nodes are available: 5 node(s) had volume node affinity "
                    "conflict."
                ),
            ),
            (
                (
                    "0/3 nodes are available: 3 node(s) didn't match pod topology "
                    "spread constraints."
                ),
                (
                    "0/5 nodes are available: 5 node(s) didn't match pod topology "
                    "spread constraints."
                ),
            ),
            (
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureA, FeatureB."
                ),
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureB, FeatureA."
                ),
            ),
            (
                (
                    "0/4 nodes are available: 3 Insufficient cpu, "
                    "1 Insufficient memory. custom post-filter result"
                ),
                (
                    "0/4 nodes are available: 3 Insufficient memory, "
                    "1 Insufficient cpu. custom post-filter result"
                ),
            ),
        ],
        ids=[
            "node-counts",
            "filter-order",
            "preemption-counts-and-order",
            "count-only-preemption",
            "general-postfilter-preemption",
            "prefilter-preemption",
            "dotted-taint-counts",
            "node-affinity-counts",
            "volume-node-affinity-counts",
            "topology-spread-counts",
            "node-declared-feature-order",
            "filter-order-with-postfilter",
        ],
    )
    def test_dedupe_key_normalizes_equivalent_scheduler_messages(
        self, first_detail: str, second_detail: str
    ):
        first = _unschedulable_diagnosis(first_detail)
        second = _unschedulable_diagnosis(second_detail)
        assert first._dedupe_key() == second._dedupe_key()

    @pytest.mark.parametrize(
        ("first_detail", "second_detail"),
        [
            (
                "0/3 nodes are available: 3 Insufficient cpu.",
                "scheduler report: 0/3 nodes are available: 3 Insufficient cpu.",
            ),
            (
                "0/3 nodes are available: 3 Insufficient cpu, 2",
                "0/5 nodes are available: 5 Insufficient cpu, 2",
            ),
            (
                "0/3 nodes are available: 3 custom plugin reason.",
                "0/5 nodes are available: 5 custom plugin reason.",
            ),
            (
                "0/3 nodes are available: FutureSchedulerPlugin changed its wording.",
                "0/5 nodes are available: FutureSchedulerPlugin changed its wording.",
            ),
            (
                (
                    "0/1 nodes are available: 1 custom plugin observed node "
                    "declared features check failed - unsatisfied requirements: "
                    "FeatureA, FeatureB."
                ),
                (
                    "0/1 nodes are available: 1 custom plugin observed node "
                    "declared features check failed - unsatisfied requirements: "
                    "FeatureB, FeatureA."
                ),
            ),
            (
                (
                    "0/1 nodes are available: 1 cannot allocate all claims. "
                    "preemption: scheduler report: 0/1 nodes are available: "
                    "1 Preemption is not helpful for scheduling."
                ),
                (
                    "0/2 nodes are available: 2 cannot allocate all claims. "
                    "preemption: scheduler report: 0/2 nodes are available: "
                    "2 Preemption is not helpful for scheduling."
                ),
            ),
            (
                (
                    "0/1 nodes are available: 1 cannot allocate all claims. "
                    "preemption: 0/1 nodes are available: 1 Preemption is not "
                    "helpful for scheduling."
                ),
                (
                    "0/1 nodes are available: 1 cannot allocate all claims. "
                    "preemption: 0/1 nodes are available: 1 Preemption is not "
                    "helpful for scheduling.."
                ),
            ),
        ],
        ids=[
            "changed-outer-scaffold",
            "incomplete-filter-histogram",
            "unrecognized-filter-reason",
            "unrecognized-prefilter-reason",
            "embedded-node-declared-features-prefix",
            "malformed-nested-preemption",
            "extra-preemption-terminator",
        ],
    )
    def test_dedupe_key_preserves_unrecognized_scheduler_messages(
        self, first_detail: str, second_detail: str
    ):
        first = _unschedulable_diagnosis(first_detail)
        second = _unschedulable_diagnosis(second_detail)
        assert first._dedupe_key() != second._dedupe_key()

    @pytest.mark.parametrize(
        ("first_detail", "second_detail"),
        [
            (
                "0/3 nodes are available: 3 Insufficient cpu.",
                "0/3 nodes are available: 3 Insufficient ephemeral-storage.",
            ),
            (
                (
                    "0/3 nodes are available: 3 node(s) had untolerated taint "
                    "{gpu-tier: 1}."
                ),
                (
                    "0/3 nodes are available: 3 node(s) had untolerated taint "
                    "{gpu-tier: 2}."
                ),
            ),
            (
                (
                    "0/3 nodes are available: 3 node(s) had untolerated taint "
                    "{node-role.kubernetes.io/master: }."
                ),
                (
                    "0/3 nodes are available: 3 node(s) had untolerated taint "
                    "{node-role.kubernetes.io/worker: }."
                ),
            ),
            (
                (
                    "0/3 nodes are available: 3 Insufficient example.com/gpu, "
                    "2 Insufficient vendor.io/fpga."
                ),
                (
                    "0/3 nodes are available: 3 Insufficient example.io/fpga, "
                    "2 Insufficient vendor.com/gpu."
                ),
            ),
            (
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureA, FeatureB."
                ),
                (
                    "0/1 nodes are available: 1 node declared features check failed "
                    "- unsatisfied requirements: FeatureA, FeatureC."
                ),
            ),
            (
                "0/1 nodes are available: policy blocked.",
                "0/1 nodes are available: 1 policy blocked.",
            ),
            (
                "0/2 nodes are available: 1 policy A. policy B",
                "0/2 nodes are available: 1 policy B. policy A",
            ),
        ],
        ids=[
            "resource-cause",
            "taint-value",
            "dotted-taint-key",
            "dotted-resource-name",
            "node-declared-feature-membership",
            "prefilter-vs-filter",
            "filter-vs-postfilter",
        ],
    )
    def test_dedupe_key_preserves_meaningful_scheduler_changes(
        self, first_detail: str, second_detail: str
    ):
        first = _unschedulable_diagnosis(first_detail)
        second = _unschedulable_diagnosis(second_detail)
        assert first._dedupe_key() != second._dedupe_key()

    def test_dedupe_key_separates_prefilter_and_post_filter(self):
        first = _unschedulable_diagnosis(
            "0/3 nodes are available: Node(s) failed PreFilter plugin "
            "FalsePreFilter. Error running PostFilter plugin FailedPostFilter"
        )
        changed_post_filter = _unschedulable_diagnosis(
            "0/3 nodes are available: Node(s) failed PreFilter plugin "
            "FalsePreFilter. Error running PostFilter plugin OtherPostFilter"
        )
        assert (
            "prefilter: Node(s) failed PreFilter plugin FalsePreFilter"
            in first._dedupe_key()
        )
        assert (
            "postfilter: Error running PostFilter plugin FailedPostFilter"
            in first._dedupe_key()
        )
        assert first._dedupe_key() != changed_post_filter._dedupe_key()
