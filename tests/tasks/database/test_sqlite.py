import os

import pytest

from prefect.tasks.database.sqlite import SQLiteQuery, SQLiteScript


class TestSQLiteQuery:
    def test_run_with_no_db(self):
        sqlite_query = SQLiteQuery(query="SELECT * FROM table")

        msg_match = "The db must be specified"
        with pytest.raises(ValueError, match=msg_match):
            sqlite_query.run()

    def test_run_with_no_query(self):
        sqlite_query = SQLiteQuery(db="database.db")

        msg_match = "The query string must be specified"
        with pytest.raises(ValueError, match=msg_match):
            sqlite_query.run()

    def test_run_with_no_param_data(self):
        sqlite_query = SQLiteQuery(
            db="database.db", query="SELECT * FROM table WHERE ?"
        )

        msg_match = "The data inputs must be specified as a tuple if query"
        with pytest.raises(ValueError, match=msg_match):
            sqlite_query.run()


class TestSQLiteScript:
    def test_run_with_no_db(self):
        sqlite_script = SQLiteScript(script="SELECT * FROM table")

        msg_match = "The db must be specified"
        with pytest.raises(ValueError, match=msg_match):
            sqlite_script.run()

    def test_run_with_no_script(self):
        sqlite_script = SQLiteScript(db="database.db")

        msg_match = "The query script string must be specified"
        with pytest.raises(ValueError, match=msg_match):
            sqlite_script.run()


def test_sqlite_create_insert_select():
    """
    Tests both SQLiteQuery and SQLiteScript
    """
    script = """
        CREATE TABLE IF NOT EXISTS book(
            title,
            author,
            published
        );

        INSERT INTO book(title, author, published)
        values (
            'Prefection',
            'Prefectionist',
            2022
        );
    """
    db = "test_sqlite.db"
    try:
        # insert data
        SQLiteScript(db).run(script=script)

        # parameterized query
        query = "SELECT * FROM book WHERE published = ? AND author = ?;"
        data = (2022, "Prefectionist")
        result = SQLiteQuery(db).run(query=query, data=data)
        assert result == [("Prefection", "Prefectionist", 2022)]
    finally:
        os.remove(db)
