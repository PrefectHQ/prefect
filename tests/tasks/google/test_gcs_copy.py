from unittest.mock import MagicMock

import pytest
from google.cloud.exceptions import NotFound

import prefect
from prefect.tasks.google import GCSCopy
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_initializes_with_defaults(self):
        task = GCSCopy()
        assert task.source_bucket is None
        assert task.source_blob is None
        assert task.dest_bucket is None
        assert task.dest_blob is None
        assert task.project is None

    def test_additional_kwargs_passed_upstream(self):
        task = GCSCopy(name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize(
        "attr",
        [
            "source_bucket",
            "source_blob",
            "dest_bucket",
            "dest_blob",
            "credentials_secret",
            "project",
        ],
    )
    def test_initializes_attr_from_kwargs(self, attr):
        task = GCSCopy(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"


class TestRuntimeValidation:
    def test_missing_source_bucket(self):
        with pytest.raises(ValueError):
            GCSCopy().run(source_blob="s", dest_bucket="d", dest_blob="d")

    def test_missing_source_blob(self):
        with pytest.raises(ValueError):
            GCSCopy().run(source_bucket="s", dest_bucket="d", dest_blob="d")

    def test_missing_dest_bucket(self):
        with pytest.raises(ValueError):
            GCSCopy().run(source_bucket="s", source_blob="s", dest_blob="d")

    def test_missing_dest_blob(self):
        with pytest.raises(ValueError):
            GCSCopy().run(source_bucket="s", source_blob="s", dest_bucket="d")

    def test_same_source_and_dest(self):
        with pytest.raises(ValueError):
            GCSCopy().run(
                source_bucket="s", source_blob="s", dest_bucket="s", dest_blob="s"
            )


# deprecated tests of `credentials_secret`
class TestCredentialsandProjects_DEPRECATED:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = GCSCopy(
            source_bucket="s",
            source_blob="s",
            dest_bucket="d",
            dest_blob="d",
            credentials_secret="GOOGLE_APPLICATION_CREDENTIALS",
        )

        creds_loader = MagicMock()
        monkeypatch.setattr("prefect.tasks.google.storage.Credentials", creds_loader)
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", MagicMock())

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS=42)):
            task.run()

        assert creds_loader.from_service_account_info.call_args[0][0] == 42

    def test_project_is_pulled_from_creds_and_can_be_overriden_at_anytime(
        self, monkeypatch
    ):
        task = GCSCopy(
            source_bucket="s",
            source_blob="s",
            dest_bucket="d",
            dest_blob="d",
            credentials_secret="GOOGLE_APPLICATION_CREDENTIALS",
        )
        task_proj = GCSCopy(
            source_bucket="s",
            source_blob="s",
            dest_bucket="d",
            dest_blob="d",
            project="test-init",
            credentials_secret="GOOGLE_APPLICATION_CREDENTIALS",
        )

        client = MagicMock()
        service_account_info = MagicMock(return_value=MagicMock(project_id="default"))
        monkeypatch.setattr(
            "prefect.tasks.google.storage.Credentials",
            MagicMock(from_service_account_info=service_account_info),
        )
        monkeypatch.setattr("prefect.tasks.google.storage.storage.Client", client)

        with prefect.context(secrets=dict(GOOGLE_APPLICATION_CREDENTIALS={})):
            task.run()
            task_proj.run()
            task_proj.run(**{"project": "run-time"})

        x, y, z = client.call_args_list

        assert x[1]["project"] == "default"  ## pulled from credentials
        assert y[1]["project"] == "test-init"  ## pulled from init
        assert z[1]["project"] == "run-time"  ## pulled from run kwarg
