import pytest

from prefect.tasks.exasol import (
    ExasolExecute,
    ExasolExportToFile,
    ExasolFetch,
    ExasolImportFromIterable,
)


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
