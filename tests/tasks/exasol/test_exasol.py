from unittest.mock import patch

import pytest

from prefect.tasks.exasol import (
    ExasolExecute,
    ExasolExportToFile,
    ExasolFetch,
    ExasolImportFromIterable,
)
import prefect
from prefect.utilities.configuration import set_temporary_config


class TestExasolExecute:
    def test_construction(self):
        task = ExasolExecute(dsn="test:12345")
        assert task.commit
        assert not task.autocommit

    def test_no_dsn(self):
        with pytest.raises(ValueError, match=r"A dsn string must be provided."):
            ExasolExportToFile().run(user="test", password="test")

    def test_query_string_must_be_provided(self):
        task = ExasolExecute(dsn="test:12345")
        with pytest.raises(ValueError, match="A query string must be provided."):
            task.run(user="test", password="test")

    @patch("prefect.tasks.exasol.exasol.pyexasol.connect", autospec=True)
    def test_secrets(self, mock_exa):
        task = ExasolExecute(
            dsn_secret="DSN_SEC", user_secret="USR_SEC", password_secret="PWD_SEC"
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(DSN_SEC="server:1234", USR_SEC="user", PWD_SEC="pwd123")
            ):
                task.run(query="SELECT * FROM DUAL;")
                mock_exa.assert_called_once_with(
                    dsn="server:1234", user="user", password="pwd123", autocommit=False
                )


class TestExasolFetch:
    def test_construction(self):
        task = ExasolFetch(dsn="test:12345")
        assert task.fetch == "one"
        assert task.fetch_size == 10

    def test_no_dsn(self):
        with pytest.raises(ValueError, match=r"A dsn string must be provided."):
            ExasolExportToFile().run(user="test", password="test")

    def test_query_string_must_be_provided(self):
        task = ExasolFetch(dsn="test:12345")
        with pytest.raises(ValueError, match="A query string must be provided."):
            task.run(user="test", password="test")

    def test_bad_fetch_param_raises(self):
        task = ExasolFetch(dsn="test:12345")
        with pytest.raises(
            ValueError,
            match=r"The 'fetch' parameter must be one of the following - \('one', 'many', 'val', 'all'\)",
        ):
            task.run(
                user="test",
                password="test",
                query="SELECT * FROM some_table",
                fetch="not a valid parameter",
            )

    @patch("prefect.tasks.exasol.exasol.pyexasol.connect", autospec=True)
    def test_secrets(self, mock_exa):
        task = ExasolFetch(
            dsn_secret="DSN_SEC", user_secret="USR_SEC", password_secret="PWD_SEC"
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(DSN_SEC="server:1234", USR_SEC="user", PWD_SEC="pwd123")
            ):
                task.run(query="SELECT * FROM DUAL;", fetch="one")
                mock_exa.assert_called_once_with(
                    dsn="server:1234", user="user", password="pwd123"
                )


class TestExasolImportFromIterable:
    def test_construction(self):
        task = ExasolImportFromIterable(dsn="test:12345")
        assert task.commit
        assert not task.autocommit

    def test_no_dsn(self):
        with pytest.raises(ValueError, match=r"A dsn string must be provided."):
            ExasolExportToFile().run(user="test", password="test")

    def test_no_data(self):
        task = ExasolImportFromIterable(dsn="test:12345")
        with pytest.raises(ValueError, match=r"Import Data must be provided."):
            task.run(user="test", password="test")

        with pytest.raises(ValueError, match=r"Import Data must be provided."):
            task.run(user="test", password="test", data=[])

    def test_no_table(self):
        task = ExasolImportFromIterable(dsn="test:12345")
        with pytest.raises(ValueError, match=r"Target table must be provided."):
            task.run(user="test", password="test", data=[(1, 2), (2, 3)])

    @patch("prefect.tasks.exasol.exasol.pyexasol.connect", autospec=True)
    def test_secrets(self, mock_exa):
        task = ExasolImportFromIterable(
            dsn_secret="DSN_SEC", user_secret="USR_SEC", password_secret="PWD_SEC"
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(DSN_SEC="server:1234", USR_SEC="user", PWD_SEC="pwd123")
            ):
                task.run(
                    target_schema="TEST", target_table="A_TAB", data=[(1, 2), (2, 3)]
                )
                mock_exa.assert_called_once_with(
                    dsn="server:1234", user="user", password="pwd123", autocommit=False
                )


class TestExasolExportToFile:
    def test_no_dsn(self):
        with pytest.raises(ValueError, match=r"A dsn string must be provided."):
            ExasolExportToFile().run(user="test", password="test")

    def test_no_destination(self):
        with pytest.raises(ValueError, match=r"A destination must be provided."):
            ExasolExportToFile(dsn="test:12345").run(user="test", password="test")

    def test_no_query_or_table(self):
        with pytest.raises(ValueError, match=r"A query or a table must be provided."):
            ExasolExportToFile(dsn="test:12345").run(
                user="test", password="test", destination="/some/path/file.csv"
            )

    @patch("prefect.tasks.exasol.exasol.pyexasol.connect", autospec=True)
    def test_secrets(self, mock_exa):
        task = ExasolExportToFile(
            dsn_secret="DSN_SEC", user_secret="USR_SEC", password_secret="PWD_SEC"
        )

        with set_temporary_config({"cloud.use_local_secrets": True}):
            with prefect.context(
                secrets=dict(DSN_SEC="server:1234", USR_SEC="user", PWD_SEC="pwd123")
            ):
                task.run(query_or_table="TEST.A_TAB", destination="/some/path/file.csv")
                mock_exa.assert_called_once_with(
                    dsn="server:1234", user="user", password="pwd123"
                )
