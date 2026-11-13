import json
import subprocess
import sys
from textwrap import dedent

import pytest


@pytest.mark.parametrize("is_async", [False, True], ids=["sync", "async"])
@pytest.mark.parametrize(
    "method, expected",
    [
        ("fetch_one", [[1], [2], None]),
        ("fetch_many", [[[1]], [[2]], []]),
        ("fetch_all", [[[1], [2]], [], []]),
    ],
)
def test_first_parameterized_fetch_reuses_cursor(is_async, method, expected):
    # A fresh process matters: previous queries can initialize SQLAlchemy's
    # shared type caches and hide the first-query regression.
    script = dedent(
        """
        import asyncio
        import json
        import sys

        from prefect_sqlalchemy import AsyncSqlAlchemyConnector, SqlAlchemyConnector

        method = sys.argv[1]
        query = "SELECT :value UNION ALL SELECT :value + 1 ORDER BY 1"
        kwargs = {"parameters": {"value": 1}}
        if method == "fetch_many":
            kwargs["size"] = 1

        def normalize(result):
            if method == "fetch_one":
                return None if result is None else tuple(result)
            return [tuple(row) for row in result]

        async def run_async():
            async with AsyncSqlAlchemyConnector(
                connection_info="sqlite+aiosqlite:///:memory:"
            ) as connector:
                fetch = getattr(connector, method)
                return [normalize(await fetch(query, **kwargs)) for _ in range(3)]

        def run_sync():
            with SqlAlchemyConnector(
                connection_info="sqlite+pysqlite:///:memory:"
            ) as connector:
                fetch = getattr(connector, method)
                return [normalize(fetch(query, **kwargs)) for _ in range(3)]

        result = asyncio.run(run_async()) if sys.argv[2] == "async" else run_sync()
        print(json.dumps(result))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, method, "async" if is_async else "sync"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize("is_async", [False, True], ids=["sync", "async"])
def test_fetch_cache_distinguishes_adapted_parameter_types(is_async):
    # SQLite adapters are process-global, so isolate them from the rest of the
    # suite. Both values are valid inputs but have different database meanings.
    script = dedent(
        """
        import asyncio
        import json
        import sqlite3
        import sys

        from prefect_sqlalchemy import AsyncSqlAlchemyConnector, SqlAlchemyConnector

        sqlite3.register_adapter(tuple, lambda value: "tuple")
        sqlite3.register_adapter(list, lambda value: "list")
        values = [(1, 2), [1, 2]]

        async def run_async():
            async with AsyncSqlAlchemyConnector(
                connection_info="sqlite+aiosqlite:///:memory:"
            ) as connector:
                return [
                    [tuple(row) for row in await connector.fetch_all(
                        "SELECT :value", parameters={"value": value}
                    )]
                    for value in values
                ]

        def run_sync():
            with SqlAlchemyConnector(
                connection_info="sqlite+pysqlite:///:memory:"
            ) as connector:
                return [
                    [tuple(row) for row in connector.fetch_all(
                        "SELECT :value", parameters={"value": value}
                    )]
                    for value in values
                ]

        result = asyncio.run(run_async()) if sys.argv[1] == "async" else run_sync()
        print(json.dumps(result))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, "async" if is_async else "sync"],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [[["tuple"]], [["list"]]]
