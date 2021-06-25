import pytest
from pathlib import Path
from unittest.mock import MagicMock

import snowflake.connector as sf
from prefect.tasks.snowflake import SnowflakeQuery, SnowflakeQueriesFromFile


@pytest.fixture
def sql_file(tmpdir):
    # write a temporary file that holds a query for testing
    query = """
        SHOW DATABASES;
        USE DEMO_DB;
    """
    p = Path(tmpdir / "test_sql.sql")
    p.write_text(query)
    return tmpdir / "test_sql.sql"


class TestSnowflakeQuery:
    def test_construction(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        assert task.autocommit is None

    def test_runtime(self, monkeypatch):
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection, cursor=cursor)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            "TESTDB"
        ]

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        # task needs to allow for runtime arguments
        output = SnowflakeQuery().run(
            account="test", user="test", password="test", query="SHOW DATABASES"
        )

        assert output == ["TESTDB"]

    def test_query_string_must_be_provided(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_execute_error_must_pass_through(self, monkeypatch):
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection, cursor=cursor)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # database cursors can be ugly to mock given  the use of __enter__
        cursor.return_value.__enter__.return_value.execute.side_effect = (
            sf.DatabaseError("Invalid query")
        )

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )

        with pytest.raises(sf.errors.DatabaseError, match="Invalid query"):
            task.run(query="SELECT * FROM foo")

    def test_execute_fetchall(self, monkeypatch):
        """
        Tests that the SnowflakeQuery Task calls the fetchall method on the
        cursor. This is to prevent future code edits from returning the cursor
        object because cursors are not pickleable.
        """
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection, cursor=cursor)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            "TESTDB"
        ]

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        output = SnowflakeQuery(
            account="test", user="test", password="test", query="SHOW DATABASES"
        ).run()

        assert output == ["TESTDB"]


class TestSnowflakeQueriesFromFile:
    def test_construction(self):
        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", warehouse="test"
        )
        assert task.autocommit is None

    def test_runtime_arguments(self, monkeypatch, tmpdir, sql_file):
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # link all the mocks together appropriately
        connection.execute_string.return_value = [cursor]

        # setting fetchall return
        cursor.fetchall.return_value = "TESTDB"

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        # task needs to allow for runtime arguments
        output = SnowflakeQueriesFromFile().run(
            account="test", user="test", password="test", file_path=sql_file
        )

        # The result is a list because multiple queries are executed
        assert output == ["TESTDB"]

    def test_file_path_must_be_provided(self):
        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", warehouse="test"
        )
        with pytest.raises(ValueError, match="A file path must be provided"):
            task.run()

    def test_execute_error_must_pass_through(self, monkeypatch, tmpdir, sql_file):
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # setting error
        connection.execute_string.side_effect = sf.DatabaseError("Invalid query")

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        task = SnowflakeQueriesFromFile(
            account="test", user="test", password="test", warehouse="test"
        )

        with pytest.raises(sf.errors.DatabaseError, match="Invalid query"):
            task.run(file_path=sql_file)

    def test_execute_fetchall(self, monkeypatch, tmpdir, sql_file):
        """
        Tests that the SnowflakeQueryFromTime Task calls the fetchall method on the
        cursor. This is to prevent future code edits from returning the cursor
        object because cursors are not pickleable.
        """
        cursor = MagicMock(spec=sf.DictCursor)
        connection = MagicMock(spec=sf.SnowflakeConnection)
        snowflake_module_connect_method = MagicMock(return_value=connection)
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        # link all the mocks together appropriately
        connection.execute_string.return_value = [cursor]

        # setting fetchall return
        cursor.fetchall.return_value = "TESTDB"

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        output = SnowflakeQueriesFromFile(
            account="test", user="test", password="test"
        ).run(file_path=sql_file)

        # The result is a list because multiple queries are executed
        assert output == ["TESTDB"]
