from unittest.mock import MagicMock

import pytest

import prefect
from prefect.tasks.dropbox import DropboxDownload
from prefect.utilities.configuration import set_temporary_config


class TestInitialization:
    def test_initializes_with_defaults(self):
        task = DropboxDownload()
        assert task.path == None

    def test_additional_kwargs_passed_upstream(self):
        task = DropboxDownload(path="", name="test-task", checkpoint=True, tags=["bob"])
        assert task.name == "test-task"
        assert task.checkpoint is True
        assert task.tags == {"bob"}

    @pytest.mark.parametrize("attr", ["path"])
    def test_download_initializes_attr_from_kwargs(self, attr):
        task = DropboxDownload(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"


class TestCredentials:
    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = DropboxDownload(path="test", access_token_secret="DROPBOX_ACCESS_TOKEN")

        dbx = MagicMock()
        monkeypatch.setattr("prefect.tasks.dropbox.dropbox.dropbox.Dropbox", dbx)

        with prefect.context(secrets=dict(DROPBOX_ACCESS_TOKEN="HI")):
            task.run()

        assert dbx.call_args[0][0] == "HI"

    def test_non_dropbox_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = DropboxDownload(path="test", access_token_secret="DROPBOX_ACCESS_TOKEN")

        dbx = MagicMock()
        monkeypatch.setattr("prefect.tasks.dropbox.dropbox.dropbox.Dropbox", dbx)

        with prefect.context(
            secrets=dict(DROPBOX_ACCESS_TOKEN="HI", TEST_SECRET="BYE")
        ):
            task.run()
            task.run(access_token_secret="TEST_SECRET")

        first_call, second_call = dbx.call_args_list
        assert first_call[0][0] == "HI"
        assert second_call[0][0] == "BYE"
