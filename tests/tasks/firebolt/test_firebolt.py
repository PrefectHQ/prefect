from unittest.mock import MagicMock

import pytest
import firebolt.db.connection as fb_conn

from prefect.tasks.firebolt.firebolt import FireboltQuery


class TestFireboltQuery:
    # test to check if the connection object has been created
    def test_construction(self):
        task = FireboltQuery(
            database="test",
            username="test",
            password="test",
            engine_name="test",
            api_endpoint="test",
            query="test",
        )
        assert task.engine_url is None

    # test to check if there are missing required parameters
    def test_required_params(self):
        # raises Value error if engine name is not provided
        with pytest.raises(ValueError, match="An engine name must be provided"):
            FireboltQuery().run(database="test", username="test", password="test", engine_url=None,
                                api_endpoint="test", query="test")
        # raises Value error if database name is not provided
        with pytest.raises(ValueError, match="A database name must be provided"):
            FireboltQuery().run(username="test", password="test", engine_name="test", engine_url=None,
                                api_endpoint="test", query="test")
        # raises Value error if username is not provided
        with pytest.raises(ValueError, match="User name must be provided"):
            FireboltQuery().run(database="test", password="test", engine_name="test", engine_url=None,
                                api_endpoint="test", query="test")
        # raises Value error if password is not provided
        with pytest.raises(ValueError, match="A password must be provided"):
            FireboltQuery().run(database="test", username="test", engine_name="test", engine_url=None,
                                api_endpoint="test", query="test")
        # raises Value error if api_endpoint is not provided
        with pytest.raises(ValueError, match="An api endpoint must be provided"):
            FireboltQuery().run(database="test", username="test", password="test", engine_name="test",
                                engine_url=None, query="test")
        # raises Value error if query is not provided
        with pytest.raises(ValueError, match="A query string must be provided"):
            FireboltQuery().run(database="test", username="test", password="test", engine_name="test",
                                engine_url=None, api_endpoint="test")

    # test to check if the ddl/dml query was executed
    def test_execute_query(self, monkeypatch):
        """
        Tests that the FireboltQuery Task calls the execute method on the cursor.
        """
        firebolt_conn = MagicMock()
        connection = MagicMock(spec=fb_conn.Connection)
        cursor = MagicMock(spec=fb_conn.Cursor)

        # link all the mocks together appropriately
        firebolt_conn.return_value = connection
        connection.cursor = cursor

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value = -1

        firebolt_connection = MagicMock(connect=firebolt_conn)

        monkeypatch.setattr(
            "prefect.tasks.firebolt.firebolt.firebolt_conn", firebolt_connection
        )

        query = "SHOW DATABASES"

        output = FireboltQuery(
            database="test",
            username="test",
            password="test",
            engine_name="test",
            engine_url=None,
            api_endpoint="test",
            query=query,
        ).run()

        assert output == []

    # test to check if the query was executed and metadata was retrieved from database
    def test_execute_fetchall(self, monkeypatch):
        """
        Tests that the FireboltQuery Task calls the fetchall method on the cursor.
        """

        firebolt_conn = MagicMock()
        connection = MagicMock(spec=fb_conn.Connection)
        cursor = MagicMock(spec=fb_conn.Cursor)

        # link all the mocks together appropriately
        firebolt_conn.return_value = connection
        connection.cursor = cursor

        # setting fetchall return
        cursor.return_value.__enter__.return_value.execute.return_value = 1
        cursor.return_value.__enter__.return_value.fetchall.return_value = ["TESTDB"]

        firebolt_connection = MagicMock(connect=firebolt_conn)

        monkeypatch.setattr(
            "prefect.tasks.firebolt.firebolt.firebolt_conn", firebolt_connection
        )

        query = "SHOW DATABASES"

        output = FireboltQuery(
            database="test",
            username="test",
            password="test",
            engine_name="test",
            engine_url=None,
            api_endpoint="test",
            query=query,
        ).run()
        assert output == ["TESTDB"]
