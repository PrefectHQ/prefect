from unittest.mock import MagicMock

import pytest

import snowflake.connector as sf
from prefect.tasks.snowflake import SnowflakeQuery


class TestSnowflakeQuery:
    def test_construction(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        assert task.autocommit is None

    def test_query_string_must_be_provided(self):
        task = SnowflakeQuery(
            account="test", user="test", password="test", warehouse="test"
        )
        with pytest.raises(ValueError, match="A query string must be provided"):
            task.run()

    def test_execute_error_must_pass_through(self, monkeypatch):
        snowflake_module_connect_method = MagicMock()
        connection = MagicMock(spec=sf.SnowflakeConnection)
        cursor = MagicMock(spec=sf.DictCursor)

        # link all the mocks together appropriately
        snowflake_module_connect_method.return_value = connection
        connection.cursor = cursor

        # database cursors can be ugly to mock given  the use of __enter__
        cursor.return_value.__enter__.return_value.execute.side_effect = (
            sf.DatabaseError("Invalid query")
        )
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

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
        object because that cursors are not pickleable.
        """
        snowflake_module_connect_method = MagicMock()
        connection = MagicMock(spec=sf.SnowflakeConnection)
        cursor = MagicMock(spec=sf.DictCursor)

        # link all the mocks together appropriately
        snowflake_module_connect_method.return_value = connection
        connection.cursor = cursor

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
            "TESTDB"
        ]
        snowflake_connector_module = MagicMock(connect=snowflake_module_connect_method)

        monkeypatch.setattr(
            "prefect.tasks.snowflake.snowflake.sf", snowflake_connector_module
        )

        query = "SHOW DATABASES"
        output = SnowflakeQuery(
            account="test", user="test", password="test", query=query
        ).run()

        assert output == ["TESTDB"]
