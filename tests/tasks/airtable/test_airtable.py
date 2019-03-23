import pytest
from unittest.mock import MagicMock

import prefect
from prefect.tasks.airtable import WriteAirtableRow
from prefect.utilities.configuration import set_temporary_config


class TestWriteAirtableRow:
    def test_initialize_with_nothing_sets_defaults(self):
        task = WriteAirtableRow()
        assert task.base_key is None
        assert task.table_name is None
        assert task.credentials_secret is "airtable_api_key"

    def test_initialize_kwargs_are_processed(self):
        task = WriteAirtableRow(checkpoint=True, name="test")
        assert task.name == "test"
        assert task.checkpoint is True

    @pytest.mark.parametrize("attr", ["base_key", "table_name", "credentials_secret"])
    def test_initializes_attr_from_kwargs(self, attr):
        task = WriteAirtableRow(**{attr: "my-value"})
        assert getattr(task, attr) == "my-value"

    def test_creds_are_pulled_from_secret_at_runtime(self, monkeypatch):
        task = WriteAirtableRow()

        airtable = MagicMock()
        monkeypatch.setattr("prefect.tasks.airtable.airtable.airtable", airtable)

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(secrets=dict(airtable_api_key="key")):
                task.run({}, base_key="a", table_name="b")

        assert airtable.Airtable.call_args[0] == ("a", "b", "key")

