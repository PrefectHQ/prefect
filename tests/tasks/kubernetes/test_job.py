import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.kubernetes import (
    CreateNamespacedJob,
    DeleteNamespacedJob,
    ListNamespacedJob,
    PatchNamespacedJob,
    ReadNamespacedJob,
    ReplaceNamespacedJob,
)
from prefect.utilities.configuration import set_temporary_config


class TestCreateNamespacedJobTask:
    def test_empty_initialization(self):
        task = CreateNamespacedJob()
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_body_raises_error(self):
        task = CreateNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = CreateNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "test"})
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"test": "b"})
        assert batchapi.create_namespaced_job.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"a": "test"})

        assert batchapi.create_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = CreateNamespacedJob()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"test": "a"})
        assert batchapi.create_namespaced_job.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert batchapi.create_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"}, kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert batchapi.create_namespaced_job.call_args[1]["a"] == "test"
        assert batchapi.create_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = CreateNamespacedJob(body={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert batchapi.create_namespaced_job.call_args[1]["test"] == "a"


class TestDeleteNamespacedJobTask:
    def test_empty_initialization(self):
        task = DeleteNamespacedJob()
        assert not task.job_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_name_raises_error(self):
        task = DeleteNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = DeleteNamespacedJob()
        with pytest.raises(ValueError):
            task.run(job_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = DeleteNamespacedJob(job_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = DeleteNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert batchapi.delete_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = DeleteNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert batchapi.delete_namespaced_job.call_args[1]["a"] == "test"
        assert batchapi.delete_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = DeleteNamespacedJob(job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert batchapi.delete_namespaced_job.call_args[1]["test"] == "a"


class TestListNamespacedJobTask:
    def test_empty_initialization(self):
        task = ListNamespacedJob()
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
        task = ListNamespacedJob(
            namespace="test",
            kube_kwargs={"test": "test"},
            kubernetes_api_key_secret="test",
        )
        assert task.namespace == "test"
        assert task.kube_kwargs == {"test": "test"}
        assert task.kubernetes_api_key_secret == "test"

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ListNamespacedJob()
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ListNamespacedJob(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert batchapi.list_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ListNamespacedJob(kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert batchapi.list_namespaced_job.call_args[1]["a"] == "test"
        assert batchapi.list_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ListNamespacedJob()

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert batchapi.list_namespaced_job.call_args[1]["test"] == "a"


class TestPatchNamespacedJobTask:
    def test_empty_initialization(self):
        task = PatchNamespacedJob()
        assert not task.job_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_body_raises_error(self):
        task = PatchNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = PatchNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_job_name_raises_error(self):
        task = PatchNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, job_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = PatchNamespacedJob(body={"test": "test"}, job_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedJob(body={"test": "a"}, job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"test": "b"})
        assert batchapi.patch_namespaced_job.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = PatchNamespacedJob(body={"test": "a"}, job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"a": "test"})
        assert batchapi.patch_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = PatchNamespacedJob(job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"test": "a"})
        assert batchapi.patch_namespaced_job.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = PatchNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert batchapi.patch_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = PatchNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert batchapi.patch_namespaced_job.call_args[1]["a"] == "test"
        assert batchapi.patch_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = PatchNamespacedJob(body={"test": "a"}, job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert batchapi.patch_namespaced_job.call_args[1]["test"] == "a"


class TestReadNamespacedJobTask:
    def test_empty_initialization(self):
        task = ReadNamespacedJob()
        assert not task.job_name
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_name_raises_error(self):
        task = ReadNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReadNamespacedJob()
        with pytest.raises(ValueError):
            task.run(job_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReadNamespacedJob(job_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReadNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert batchapi.read_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReadNamespacedJob(job_name="test", kube_kwargs={"test": "a"})

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert batchapi.read_namespaced_job.call_args[1]["a"] == "test"
        assert batchapi.read_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReadNamespacedJob(job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert batchapi.read_namespaced_job.call_args[1]["test"] == "a"


class TestReplaceNamespacedJobTask:
    def test_empty_initialization(self):
        task = ReplaceNamespacedJob()
        assert not task.job_name
        assert task.body == {}
        assert task.namespace == "default"
        assert task.kube_kwargs == {}
        assert task.kubernetes_api_key_secret == "KUBERNETES_API_KEY"

    def test_filled_initialization(self):
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

    def test_empty_body_raises_error(self):
        task = ReplaceNamespacedJob()
        with pytest.raises(ValueError):
            task.run()

    def test_invalid_body_raises_error(self):
        task = ReplaceNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body=None)

    def test_invalid_job_name_raises_error(self):
        task = ReplaceNamespacedJob()
        with pytest.raises(ValueError):
            task.run(body={"test": "test"}, job_name=None)

    def test_api_key_pulled_from_secret(self, monkeypatch):
        task = ReplaceNamespacedJob(body={"test": "test"}, job_name="test")
        client = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.client", client)

        conf_call = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client.Configuration", conf_call
        )
        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
                task.run()
        assert conf_call.called

    def test_body_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedJob(body={"test": "a"}, job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"test": "b"})
        assert batchapi.replace_namespaced_job.call_args[1]["body"] == {"test": "b"}

    def test_body_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedJob(body={"test": "a"}, job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"a": "test"})
        assert batchapi.replace_namespaced_job.call_args[1]["body"] == {
            "a": "test",
            "test": "a",
        }

    def test_empty_body_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedJob(job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(body={"test": "a"})
        assert batchapi.replace_namespaced_job.call_args[1]["body"] == {"test": "a"}

    def test_kube_kwargs_value_is_replaced(self, monkeypatch):
        task = ReplaceNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "b"})
        assert batchapi.replace_namespaced_job.call_args[1]["test"] == "b"

    def test_kube_kwargs_value_is_appended(self, monkeypatch):
        task = ReplaceNamespacedJob(
            body={"test": "a"}, kube_kwargs={"test": "a"}, job_name="test"
        )

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"a": "test"})
        assert batchapi.replace_namespaced_job.call_args[1]["a"] == "test"
        assert batchapi.replace_namespaced_job.call_args[1]["test"] == "a"

    def test_empty_kube_kwargs_value_is_updated(self, monkeypatch):
        task = ReplaceNamespacedJob(body={"test": "a"}, job_name="test")

        config = MagicMock()
        monkeypatch.setattr("prefect.tasks.kubernetes.job.config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.tasks.kubernetes.job.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        task.run(kube_kwargs={"test": "a"})
        assert batchapi.replace_namespaced_job.call_args[1]["test"] == "a"
