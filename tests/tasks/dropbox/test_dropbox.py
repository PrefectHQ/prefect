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
    def test_uses_access_token(self, monkeypatch):
        task = DropboxDownload(path="test")

        dbx = MagicMock()
        monkeypatch.setattr("prefect.tasks.dropbox.dropbox.dropbox.Dropbox", dbx)

        task.run(access_token="HI")

        assert dbx.call_args[0][0] == "HI"
