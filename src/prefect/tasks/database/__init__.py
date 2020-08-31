import warnings

try:
    from prefect.tasks.database.sqlite import SQLiteQuery, SQLiteScript
except ImportError:
    warnings.warn(
        "SQLite tasks require sqlite3 to be installed", UserWarning, stacklevel=2
    )
