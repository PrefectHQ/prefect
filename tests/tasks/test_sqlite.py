import pytest
import sqlite3
import tempfile
from contextlib import closing

from prefect import Flow
from prefect.tasks.database import SQLiteQueryTask, SQLiteScriptTask
from prefect.utilities.tests import raise_on_exception


sql_script = """
CREATE TABLE TEST (NUMBER INTEGER, DATA TEXT);
INSERT INTO TEST (NUMBER, DATA) VALUES
(11, 'first'),
(12, 'second'),
(13, 'third');
"""


@pytest.fixture(scope="module")
def database():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        with closing(sqlite3.connect(tmp.name)) as conn:
            with closing(conn.cursor()) as c:
                c.executescript(sql_script)
                conn.commit()
        yield tmp.name


class TestSQLiteQueryTask:
    def test_sqlite_query_task_initializes_and_runs_basic_query(self, database):
        with Flow() as f:
            task = SQLiteQueryTask(db=database)(query="SELECT * FROM TEST")
        out = f.run(return_tasks=[task])
        assert out.is_successful()
        assert out.result[task].result == [(11, "first"), (12, "second"), (13, "third")]

    def test_sqlite_query_task_initializes_with_query_and_runs(self, database):
        with Flow() as f:
            task = SQLiteQueryTask(db=database, query="SELECT * FROM TEST")()
        out = f.run(return_tasks=[task])
        assert out.is_successful()
        assert out.result[task].result == [(11, "first"), (12, "second"), (13, "third")]

    def test_sqlite_error_results_in_failed_state(self, database):
        with Flow() as f:
            task = SQLiteQueryTask(db=database, query="SELECT * FROM FOOBAR")()
        out = f.run(return_tasks=[task])
        assert out.is_failed()
        assert "no such table: FOOBAR" in str(out.result[task].result)

    def test_only_single_statement_queries_allowed(self, database):
        query = """INSERT INTO TEST (NUMBER, DATA) VALUES\n(88, "other");\nSELECT * FROM TEST;"""
        with Flow() as f:
            task = SQLiteQueryTask(db=database, query=query)()
        out = f.run(return_tasks=[task])
        assert out.is_failed()
        assert "one statement at a time" in str(out.result[task].result)


class TestSQLiteScriptTask:
    def test_sqlite_script_task_initializes_and_runs_basic_script(self, database):
        with Flow() as f:
            task = SQLiteScriptTask(db=database)(script="SELECT * FROM TEST;")
        out = f.run(return_tasks=[task])
        assert out.is_successful()
        assert out.result[task].result is None

    def test_sqlite_script_task_initializes_with_script_and_runs(self, database):
        with Flow() as f:
            task = SQLiteScriptTask(db=database, script="SELECT * FROM TEST;")()
        out = f.run(return_tasks=[task])
        assert out.is_successful()
        assert out.result[task].result is None

    def test_sqlite_error_results_in_failed_state(self, database):
        with Flow() as f:
            task = SQLiteScriptTask(db=database)(script="SELECT * FROM FOOBAR;")
        out = f.run(return_tasks=[task])
        assert out.is_failed()
        assert "no such table: FOOBAR" in str(out.result[task].result)
