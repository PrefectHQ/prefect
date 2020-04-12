from unittest.mock import MagicMock

import pytest
from google.cloud.exceptions import NotFound

import prefect
from prefect.tasks.gcp import GCSCopy
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
        ["source_bucket", "source_blob", "dest_bucket", "dest_blob", "project",],
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
