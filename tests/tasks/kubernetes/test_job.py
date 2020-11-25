from unittest.mock import MagicMock
from box import Box

import pytest

import prefect
from prefect.engine import signals
from prefect.tasks.kubernetes import (
    CreateNamespacedJob,
    DeleteNamespacedJob,
    ListNamespacedJob,
    PatchNamespacedJob,
    ReadNamespacedJob,
    ReplaceNamespacedJob,
    RunNamespacedJob,
)
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


@pytest.fixture
def api_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        "prefect.tasks.kubernetes.job.get_kubernetes_client",
        MagicMock(return_value=client),
    )
    return client


@pytest.fixture
def successful_job_status():
    job_status = MagicMock()
    job_status.status.active = None
    job_status.status.failed = None
    job_status.status.succeeded = 1
    return job_status


@pytest.fixture
def read_pod_logs(monkeypatch):
    read_pod_logs = MagicMock(return_value=None)
    monkeypatch.setattr(
        "prefect.tasks.kubernetes.pod.ReadNamespacedPodLogs.__init__", read_pod_logs
    )
    return read_pod_logs


class TestCreateNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = CreateNamespacedJob()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = CreateNamespacedJob(
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = CreateNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = CreateNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = CreateNamespacedJob(body={"test": "a"})

        task.run(body={"test": "b"})
        assert api_client.create_namespaced_job.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = CreateNamespacedJob(body={"test": "a"})

        task.run(body={"a": "test"})

        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = CreateNamespacedJob()

        task.run(body={"test": "a"})
        assert api_client.create_namespaced_job.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = CreateNamespacedJob(body={"test": "a"}, kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.create_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = CreateNamespacedJob(body={"test": "a"}, kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.create_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.create_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = CreateNamespacedJob(body={"test": "a"})

        task.run(kube_kwargs={"test": "a"})
        assert api_client.create_namespaced_job.call_args[1]["test"] == "a"


class TestDeleteNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = DeleteNamespacedJob()
        assert not task.job_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = DeleteNamespacedJob(
            job_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.job_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self, kube_secret):
        task = DeleteNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = DeleteNamespacedJob()
        with pytest.raises(ValueError):
            task.run(job_name=None)

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = DeleteNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.delete_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = DeleteNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.delete_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.delete_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = DeleteNamespacedJob(job_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.delete_namespaced_job.call_args[1]["test"] == "a"


class TestListNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = ListNamespacedJob()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ListNamespacedJob(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ListNamespacedJob(kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.list_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ListNamespacedJob(kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.list_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.list_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ListNamespacedJob()

        task.run(kube_kwargs={"test": "a"})
        assert api_client.list_namespaced_job.call_args[1]["test"] == "a"


class TestPatchNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = PatchNamespacedJob()
        assert not task.job_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = PatchNamespacedJob(
            job_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.job_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = PatchNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = PatchNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_job_name_raises_error(self, kube_secret):
        task = PatchNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, job_name=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = PatchNamespacedJob(body={"test": "a"}, job_name="test")

        task.run(body={"test": "b"})
        assert api_client.patch_namespaced_job.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = PatchNamespacedJob(body={"test": "a"}, job_name="test")

        task.run(body={"a": "test"})
        assert api_client.patch_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = PatchNamespacedJob(job_name="test")

        task.run(body={"test": "a"})
        assert api_client.patch_namespaced_job.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = PatchNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.patch_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = PatchNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.patch_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.patch_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = PatchNamespacedJob(body={"test": "a"}, job_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.patch_namespaced_job.call_args[1]["test"] == "a"


class TestReadNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = ReadNamespacedJob()
        assert not task.job_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ReadNamespacedJob(
            job_name="test",
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.job_name == "test"
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_name_raises_error(self, kube_secret):
        task = ReadNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReadNamespacedJob()
        with pytest.raises(ValueError):
            task.run(job_name=None)

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ReadNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"test": "b"})
        assert api_client.read_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ReadNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        task.run(kube_kwargs={"a": "test"})
        assert api_client.read_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.read_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ReadNamespacedJob(job_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.read_namespaced_job.call_args[1]["test"] == "a"


class TestReplaceNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = ReplaceNamespacedJob()
        assert not task.job_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = ReplaceNamespacedJob(
            job_name="test",
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.job_name == "test"
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = ReplaceNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_job_name_raises_error(self, kube_secret):
        task = ReplaceNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, job_name=None)

    def test_body_value_is_replaced(self, kube_secret, api_client):
        task = ReplaceNamespacedJob(body={"test": "a"}, job_name="test")

        task.run(body={"test": "b"})
        assert api_client.replace_namespaced_job.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, kube_secret, api_client):
        task = ReplaceNamespacedJob(body={"test": "a"}, job_name="test")

        task.run(body={"a": "test"})
        assert api_client.replace_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, kube_secret, api_client):
        task = ReplaceNamespacedJob(job_name="test")

        task.run(body={"test": "a"})
        assert api_client.replace_namespaced_job.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, kube_secret, api_client):
        task = ReplaceNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.replace_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, kube_secret, api_client):
        task = ReplaceNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.replace_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.replace_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, kube_secret, api_client):
        task = ReplaceNamespacedJob(body={"test": "a"}, job_name="test")

        task.run(kube_kwargs={"test": "a"})
        assert api_client.replace_namespaced_job.call_args[1]["test"] == "a"


class TestRunNamespacedJobTask:
    def test_empty_initialization(self, kube_secret):
        task = RunNamespacedJob()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self, kube_secret):
        task = RunNamespacedJob(
            body={"test": "test"},
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.body == {"test": "test"}
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_empty_body_raises_error(self, kube_secret):
        task = RunNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self, kube_secret):
        task = RunNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_log_level_raises_error(self, kube_secret):
        task = RunNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, log_level="invalid")

    def test_body_value_is_replaced(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob(body={"metadata": {"name": "a"}})

        task.run(body={"metadata": {"name": "b"}})
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "metadata": {"name": "b"}
        }

    def test_body_value_is_appended(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )
        task = RunNamespacedJob(body={"metadata": {"name": "a"}})

        task.run(body={"a": "test"})
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "metadata": {"name": "a"},
        }

    def test_empty_body_value_is_updated(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob()

        task.run(body={"metadata": {"name": "a"}})
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "metadata": {"name": "a"}
        }

    def test_kube_kwargs_value_is_replaced(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob(
            body={"metadata": {"name": "a"}}, kube_kwargs={"test": "a"}
        )

        task.run(kube_kwargs={"test": "b"})
        assert api_client.create_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob(
            body={"metadata": {"name": "a"}}, kube_kwargs={"test": "a"}
        )

        task.run(kube_kwargs={"a": "test"})
        assert api_client.create_namespaced_job.call_args[1]["a"] == "test"
        assert api_client.create_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob(body={"metadata": {"name": "a"}})

        task.run(kube_kwargs={"test": "a"})
        assert api_client.create_namespaced_job.call_args[1]["test"] == "a"

    def test_run_successful_path(self, kube_secret, api_client, successful_job_status):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob(body={"metadata": {"name": "success"}})
        task.run()

        assert api_client.create_namespaced_job.call_count == 1
        assert api_client.create_namespaced_job.call_args[1]["namespace"] == "default"
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "metadata": {"name": "success"}
        }

        assert api_client.read_namespaced_job_status.call_count == 1
        assert api_client.read_namespaced_job_status.call_args[1]["name"] == "success"
        assert (
            api_client.read_namespaced_job_status.call_args[1]["namespace"] == "default"
        )

        assert api_client.delete_namespaced_job.call_count == 1
        assert api_client.delete_namespaced_job.call_args[1]["name"] == "success"
        assert api_client.delete_namespaced_job.call_args[1]["namespace"] == "default"

    def test_run_successful_path_without_deleting_resources_after_completion(
        self, kube_secret, api_client, successful_job_status
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        task = RunNamespacedJob(
            body={"metadata": {"name": "success"}}, delete_job_after_completion=False
        )
        task.run()

        assert api_client.create_namespaced_job.call_count == 1
        assert api_client.create_namespaced_job.call_args[1]["namespace"] == "default"
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "metadata": {"name": "success"}
        }

        assert api_client.read_namespaced_job_status.call_count == 1
        assert api_client.read_namespaced_job_status.call_args[1]["name"] == "success"
        assert (
            api_client.read_namespaced_job_status.call_args[1]["namespace"] == "default"
        )

        assert api_client.delete_namespaced_job.call_count == 0

    def test_run_unsuccessful_path(self, kube_secret, api_client):
        unsuccessful_job_status = MagicMock()
        unsuccessful_job_status.status.active = None
        unsuccessful_job_status.status.failed = 1
        unsuccessful_job_status.status.succeeded = None

        api_client.read_namespaced_job_status = MagicMock(
            return_value=unsuccessful_job_status
        )

        task = RunNamespacedJob(body={"metadata": {"name": "failure"}})
        with pytest.raises(signals.FAIL) as failed:
            task.run()

        assert api_client.create_namespaced_job.call_count == 1
        assert api_client.create_namespaced_job.call_args[1]["namespace"] == "default"
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "metadata": {"name": "failure"}
        }

        assert api_client.read_namespaced_job_status.call_count == 1
        assert api_client.read_namespaced_job_status.call_args[1]["name"] == "failure"
        assert (
            api_client.read_namespaced_job_status.call_args[1]["namespace"] == "default"
        )

        assert api_client.delete_namespaced_job.call_count == 0

    def test_run_with_logging(
        self, kube_secret, api_client, successful_job_status, read_pod_logs
    ):
        api_client.read_namespaced_job_status = MagicMock(
            return_value=successful_job_status
        )

        api_client.list_namespaced_pod = MagicMock(
            return_value=MagicMock(
                items=[
                    Box(
                        {
                            "metadata": {"name": "test-pod"},
                            "status": {"phase": "Running"},
                        }
                    )
                ]
            )
        )

        task = RunNamespacedJob(
            body={"metadata": {"name": "success"}}, log_level="info"
        )
        task.run()

        assert api_client.create_namespaced_job.call_count == 1
        assert api_client.create_namespaced_job.call_args[1]["namespace"] == "default"
        assert api_client.create_namespaced_job.call_args[1]["body"] == {
            "metadata": {"name": "success"}
        }

        assert api_client.read_namespaced_job_status.call_count == 1
        assert api_client.read_namespaced_job_status.call_args[1]["name"] == "success"
        assert (
            api_client.read_namespaced_job_status.call_args[1]["namespace"] == "default"
        )

        assert api_client.list_namespaced_pod.call_count == 1
        assert api_client.list_namespaced_pod.call_args[1]["label_selector"].startswith(
            "controller-uid="
        )
        assert api_client.list_namespaced_pod.call_args[1]["namespace"] == "default"

        assert read_pod_logs.call_count == 1
        assert read_pod_logs.call_args[1]["pod_name"] == "test-pod"
        assert read_pod_logs.call_args[1]["namespace"] == "default"

        assert api_client.delete_namespaced_job.call_count == 1
        assert api_client.delete_namespaced_job.call_args[1]["name"] == "success"
        assert api_client.delete_namespaced_job.call_args[1]["namespace"] == "default"
