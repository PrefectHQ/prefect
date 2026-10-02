import pytest
from armada_client.armada import submit_pb2
from armada_client.typings import JobState
from prefect_armada.exceptions import ArmadaJobDefinitionError
from prefect_armada.utilities import (
    TERMINAL_JOB_STATES,
    UNSUCCESSFUL_JOB_STATES,
    _grpc_keepalive_options,
    _slugify_label_key,
    _slugify_label_value,
    _slugify_name,
    coerce_job_request_items,
    coerce_queues,
    format_job_pid,
    job_request_item_from_dict,
    job_state_from_value,
    parse_job_pid,
    pod_spec_from_dict,
    queue_from_dict,
)


class TestPodSpecFromDict:
    def test_converts_a_kubernetes_style_pod_spec(self):
        pod_spec = pod_spec_from_dict(
            {
                "restartPolicy": "Never",
                "serviceAccountName": "prefect",
                "containers": [
                    {
                        "name": "prefect-job",
                        "image": "prefecthq/prefect:3-latest",
                        "args": ["prefect", "flow-run", "execute"],
                        "env": [{"name": "PREFECT_API_URL", "value": "http://api"}],
                    }
                ],
            }
        )

        assert pod_spec.restartPolicy == "Never"
        assert pod_spec.serviceAccountName == "prefect"
        assert pod_spec.containers[0].name == "prefect-job"
        assert list(pod_spec.containers[0].args) == [
            "prefect",
            "flow-run",
            "execute",
        ]
        assert pod_spec.containers[0].env[0].name == "PREFECT_API_URL"

    def test_converts_resource_quantities_from_strings(self):
        pod_spec = pod_spec_from_dict(
            {
                "containers": [
                    {
                        "name": "prefect-job",
                        "resources": {
                            "requests": {"cpu": "500m", "memory": "512Mi"},
                            "limits": {"cpu": 2},
                        },
                    }
                ]
            }
        )

        resources = pod_spec.containers[0].resources
        assert resources.requests["cpu"].string == "500m"
        assert resources.requests["memory"].string == "512Mi"
        assert resources.limits["cpu"].string == "2"

    def test_drops_none_values(self):
        # Rendering a job template leaves optional work pool variables as None.
        pod_spec = pod_spec_from_dict(
            {
                "restartPolicy": "Never",
                "serviceAccountName": None,
                "containers": [
                    {
                        "name": "prefect-job",
                        "image": None,
                        "resources": {
                            "requests": {"cpu": None, "memory": "512Mi"},
                            "limits": {"cpu": None, "memory": None},
                        },
                    }
                ],
            }
        )

        container = pod_spec.containers[0]
        assert pod_spec.serviceAccountName == ""
        assert container.image == ""
        assert "cpu" not in container.resources.requests
        assert container.resources.requests["memory"].string == "512Mi"
        assert not container.resources.limits

    def test_raises_on_unknown_field(self):
        with pytest.raises(ArmadaJobDefinitionError, match="notAFieldOfPodSpec"):
            pod_spec_from_dict({"notAFieldOfPodSpec": True})


class TestJobRequestItemFromDict:
    @pytest.mark.parametrize("pod_spec_key", ["podSpec", "pod_spec"])
    def test_converts_a_job_request(self, pod_spec_key):
        job_request_item = job_request_item_from_dict(
            {
                "priority": 2,
                "namespace": "prefect",
                "labels": {"prefect.io/flow-run-id": "abc"},
                "annotations": {"prefect.io/flow-run-name": "run"},
                "externalJobUri": "prefect://flow-run/abc",
                pod_spec_key: {
                    "restartPolicy": "Never",
                    "containers": [{"name": "prefect-job", "image": "busybox"}],
                },
            }
        )

        assert job_request_item.priority == 2
        assert job_request_item.namespace == "prefect"
        assert job_request_item.labels == {"prefect.io/flow-run-id": "abc"}
        assert job_request_item.annotations == {"prefect.io/flow-run-name": "run"}
        assert job_request_item.external_job_uri == "prefect://flow-run/abc"
        assert job_request_item.pod_spec.containers[0].image == "busybox"

    def test_raises_on_invalid_job_request(self):
        with pytest.raises(ArmadaJobDefinitionError):
            job_request_item_from_dict({"podSpec": {"containers": "not-a-list"}})


class TestCoerceJobRequestItems:
    def test_coerces_a_single_dict(self):
        items = coerce_job_request_items({"namespace": "default"})
        assert len(items) == 1
        assert items[0].namespace == "default"

    def test_coerces_a_list_of_dicts(self):
        items = coerce_job_request_items(
            [{"namespace": "a"}, {"namespace": "b"}],
        )
        assert [item.namespace for item in items] == ["a", "b"]

    def test_passes_through_protobuf_items(self):
        item = submit_pb2.JobSubmitRequestItem(namespace="default")
        assert coerce_job_request_items(item) == [item]


class TestCoerceQueues:
    def test_converts_dicts_and_passes_through_protobuf(self):
        existing = submit_pb2.Queue(name="already-a-queue")
        queues = coerce_queues([{"name": "from-dict", "priorityFactor": 2}, existing])

        assert queues[0].name == "from-dict"
        assert queues[0].priority_factor == 2
        assert queues[1] is existing

    def test_queue_from_dict_accepts_snake_case(self):
        queue = queue_from_dict({"name": "q", "priority_factor": 3})
        assert queue.priority_factor == 3


class TestJobStateHelpers:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (JobState.RUNNING, JobState.RUNNING),
            (2, JobState.RUNNING),
            ("running", JobState.RUNNING),
            ("SUCCEEDED", JobState.SUCCEEDED),
        ],
    )
    def test_job_state_from_value(self, value, expected):
        assert job_state_from_value(value) is expected

    def test_job_state_from_value_raises_on_unknown(self):
        with pytest.raises((ValueError, KeyError)):
            job_state_from_value("not-a-state")

    def test_terminal_states(self):
        assert JobState.SUCCEEDED in TERMINAL_JOB_STATES
        assert JobState.RUNNING not in TERMINAL_JOB_STATES
        assert JobState.SUCCEEDED not in UNSUCCESSFUL_JOB_STATES
        assert UNSUCCESSFUL_JOB_STATES < TERMINAL_JOB_STATES


class TestJobPid:
    def test_round_trips(self):
        pid = format_job_pid("queue", "job-set", "job-id")
        assert pid == "queue:job-set:job-id"
        assert parse_job_pid(pid) == ("queue", "job-set", "job-id")

    @pytest.mark.parametrize("pid", ["queue:job-set", "a:b:c:d", "::", "queue::job"])
    def test_raises_on_invalid_pid(self, pid):
        with pytest.raises(ValueError, match="Invalid infrastructure_pid"):
            parse_job_pid(pid)


class TestSlugify:
    def test_slugify_name(self):
        assert _slugify_name("My Flow Run!") == "my-flow-run"
        assert _slugify_name("!!!") is None

    def test_slugify_label_key_with_prefix(self):
        assert _slugify_label_key("prefect.io/flow-run-id") == "prefect.io/flow-run-id"

    def test_slugify_label_value(self):
        assert _slugify_label_value("Some Value") == "Some-Value"


def test_grpc_keepalive_options():
    options = dict(_grpc_keepalive_options())
    assert options["grpc.keepalive_time_ms"] == 30000
    assert options["grpc.keepalive_permit_without_calls"] == 1
