import os
import sqlite3
import tempfile
from contextlib import closing

import pytest

from prefect import Flow, Parameter
from prefect.tasks.database import SQLiteQuery, SQLiteScript


sql_script = """
CREATE TABLE TEST (NUMBER INTEGER, DATA TEXT);
INSERT INTO TEST (NUMBER, DATA) VALUES
(11, 'first'),
(12, 'second'),
(13, 'third');
"""


@pytest.fixture(scope="module")
def database():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpname = os.path.join(tmpdir, "test.db")
        with closing(sqlite3.connect(tmpname)) as conn:
            with closing(conn.cursor()) as c:
                c.executescript(sql_script)
                conn.commit()
        yield tmpname


class TestSQLiteQuery:
    def test_initialization(self):
        task = SQLiteQuery()

    def test_sqlite_query_task_initializes_and_runs_basic_query(self, database):
        with Flow(name="test") as f:
            task = SQLiteQuery(db=database)(query="SELECT * FROM TEST")
        out = f.run()
        assert out.is_successful()
        assert out.result[task].result == [(11, "first"), (12, "second"), (13, "third")]

    def test_sqlite_query_task_initializes_with_query_and_runs(self, database):
        with Flow(name="test") as f:
            task = SQLiteQuery(db=database, query="SELECT * FROM TEST")()
        out = f.run()
        assert out.is_successful()
        assert out.result[task].result == [(11, "first"), (12, "second"), (13, "third")]

    def test_sqlite_error_results_in_failed_state(self, database):
        with Flow(name="test") as f:
            task = SQLiteQuery(db=database, query="SELECT * FROM FOOBAR")()
        out = f.run()
        assert out.is_failed()
        assert "no such table: FOOBAR" in str(out.result[task].result)

    def test_only_single_statement_queries_allowed(self, database):
        query = """INSERT INTO TEST (NUMBER, DATA) VALUES\n(88, "other");\nSELECT * FROM TEST;"""
        with Flow(name="test") as f:
            task = SQLiteQuery(db=database, query=query)()
        out = f.run()
        assert out.is_failed()
        assert "one statement at a time" in str(out.result[task].result)

    def test_parametrized_query(self, database):
        with Flow(name="test") as f:
            task = SQLiteQuery(db=database)(
                query="SELECT * FROM TEST WHERE NUMBER in (?, ?)", data=(12, 13)
            )
        out = f.run()
        assert out.is_successful()
        assert out.result[task].result == [(12, "second"), (13, "third")]


class TestSQLiteScript:
    def test_initialization(self):
        task = SQLiteScript()

    def test_sqlite_script_task_initializes_and_runs_basic_script(self, database):
        with Flow(name="test") as f:
            task = SQLiteScript(db=database)(script="SELECT * FROM TEST;")
        out = f.run()
        assert out.is_successful()
        assert out.result[task].result is None

    def test_sqlite_script_task_initializes_with_script_and_runs(self, database):
        with Flow(name="test") as f:
            task = SQLiteScript(db=database, script="SELECT * FROM TEST;")()
        out = f.run()
        assert out.is_successful()
        assert out.result[task].result is None

    def test_sqlite_error_results_in_failed_state(self, database):
        with Flow(name="test") as f:
            task = SQLiteScript(db=database)(script="SELECT * FROM FOOBAR;")
        out = f.run()
        assert out.is_failed()
        assert "no such table: FOOBAR" in str(out.result[task].result)


def test_composition_of_tasks(database):
    script = """CREATE TABLE TEST2 (NUM INTEGER, DATA TEXT); INSERT INTO TEST2 (NUM, DATA) VALUES\n(88, "other"); ALTER TABLE TEST2\n ADD status TEXT;"""
    with Flow(name="test") as f:
        alter = SQLiteScript(db=database)(script=script)
        task = SQLiteQuery(db=database, query="SELECT * FROM TEST2")(
            upstream_tasks=[alter]
        )
    out = f.run()
    assert out.is_successful()
    assert out.result[task].result == [(88, "other", None)]


def test_parametrization_of_tasks(database):
    with Flow(name="test") as f:
        db = Parameter("db")
        script = Parameter("script")

        script = SQLiteScript(db=database)(script=script)
        task = SQLiteQuery()(
            db=db, query="SELECT * FROM TEST WHERE NUMBER = 14", upstream_tasks=[script]
        )

    out = f.run(
        db=database, script="INSERT INTO TEST (NUMBER, DATA) VALUES (14, 'fourth')"
    )
    assert out.is_successful()
    assert out.result[task].result == [(14, "fourth")]
