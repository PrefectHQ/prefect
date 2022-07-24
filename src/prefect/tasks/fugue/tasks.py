from typing import Any, List

import fugue
import fugue_sql
from fugue.extensions.transformer.convert import _to_transformer

from prefect.core import Task
from prefect.utilities.context import context
from prefect.utilities.tasks import task

_TASK_NAME_MAX_LEN = 50


def fsql(
    query: str,
    yields: Any = None,
    engine: Any = None,
    engine_conf: Any = None,
    checkpoint: bool = True,
    **kwargs: Any
) -> dict:
    """
    Function for running Fugue SQL.

    This function generates the Prefect task that runs Fugue SQL.

    Args:
        - query (str): the Fugue SQL query
        - yields (Any): the yielded dataframes from the previous tasks, defaults to None. It
            can be a single yielded result or an array of yielded results (see example)
        - engine (Any): execution engine expression that can be recognized by Fugue, default
            to None (the default ExecutionEngine of Fugue)
        - engine_conf (Any): extra execution engine configs, defaults to None
        - checkpoint (bool): whether to checkpoint this task in Prefect, defaults to True
        - **kwargs (Any, optional): additional kwargs to pass to Fugue's `fsql` function

    References:
        - See: [Fugue SQL
            Tutorial](https://fugue-tutorials.readthedocs.io/tutorials/fugue_sql/index.html)

    Example:
        ```python
        from prefect import Flow, task
        from prefect.tasks.fugue import fsql
        import pandas as pd

        # Basic usage
        with Flow() as f:
            res1 = fsql("CREATE [[0]] SCHEMA a:int YIELD DATAFRAME AS x")
            res2 = fsql("CREATE [[1],[2]] SCHEMA a:int YIELD DATAFRAME AS y")
            fsql('''
            SELECT * FROM x UNION SELECT * FROM y
            SELECT * WHERE a<2
            PRINT
            ''', [res1, res2]) # SQL union using pandas
            fsql('''
            SELECT * FROM x UNION SELECT * FROM y
            SELECT * WHERE a<2
            PRINT
            ''', [res1, res2], engine="duckdb") # SQL union using duckdb (if installed)

        # Pass in other parameters and dataframes
        @task
        def gen_df():
            return pd.DataFrame(dict(a=[1]))

        @task
        def gen_path():
            return "/tmp/t.parquet"

        with Flow() as f:
            df = gen_df()
            path = gen_path()
            fsql('''
            SELECT a+1 AS a FROM df
            SAVE OVERWRITE {{path}}
            ''', df=df, path=path)

        # Disable checkpoint for distributed dataframes
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()

        with Flow() as f:
            # res1 needs to turn off checkpoint because it yields
            # a Spark DataFrame
            res1 = fsql('''
                CREATE [[1],[2]] SCHEMA a:int YIELD DATAFRAME AS y
            ''', engine=spark, checkpoint=False)

            # res2 doesn't need to turn off checkpoint because it yields
            # a local DataFrame (most likely Pandas DataFrame)
            res2 = fsql('''
                CREATE [[1],[2]] SCHEMA a:int YIELD LOCAL DATAFRAME AS y
            ''', engine=spark)

            # res3 doesn't need to turn off checkpoint because it yields
            # a file (the dataframe is cached in the file)
            res3 = fsql('''
                CREATE [[-1],[3]] SCHEMA a:int YIELD FILE AS z
            ''', engine=spark)

            # this step doesn't need to turn off checkpoint because it
            # doesn't have any output
            fsql('''
            SELECT * FROM x UNION SELECT * FROM y UNION SELECT * FROM z
            SELECT * WHERE a<2
            PRINT
            ''', [res1, res2, res3], engine=spark)
        ```

    Note: The best practice is always yielding files or local dataframes. If
    you want to yield a distributed dataframe such as Spark or Dask, think it twice.
    `YIELD FILE` is always preferred when Fugue SQL is running as a Prefect task.
    If you feel `YIELD FILE` is too heavy, that means your
    SQL logic may not be heavy enough to be broken into multiple tasks.
    """
    if not isinstance(query, Task):
        tn = _truncate_name(query)
    else:
        tn = "FugueSQL"

    @task(name=tn, checkpoint=checkpoint)
    def run_fsql(
        query: str,
        yields: Any = None,
        engine: Any = None,
        engine_conf: Any = None,
        **kwargs: Any
    ) -> dict:
        logger = context.get("logger")
        logger.debug(query)
        return fugue_sql.fsql(query, *_normalize_yields(yields), **kwargs).run(
            engine, engine_conf
        )

    return run_fsql(
        query=query, yields=yields, engine=engine, engine_conf=engine_conf, **kwargs
    )


def transform(
    df: Any,
    transformer: Any,
    engine: Any = None,
    engine_conf: Any = None,
    checkpoint: bool = False,
    **kwargs
) -> Any:
    """
    Function for running Fugue transform function.

    This function generates the Prefect task that runs Fugue transform.

    Args:
        - df (Any): a dataframe generated from the previous steps
        - transformer (Any): a function or class that be recognized by Fugue as a transformer
        - engine (Any): execution engine expression that can be recognized by Fugue, default
            to None (the default ExecutionEngine of Fugue)
        - engine_conf (Any): extra execution engine configs, defaults to None
        - checkpoint (bool): whether to checkpoint this task in Prefect, defaults to False
        - **kwargs (Any, optional): additional kwargs to pass to Fugue's `transform` function

    References:
        - See: [Fugue
            Transform](https://fugue-tutorials.readthedocs.io/tutorials/extensions/transformer.html)

    Example:
        ```python
        from prefect import Flow, task
        from prefect.tasks.fugue import transform, fsql
        from dask.distributed import Client
        import pandas as pd

        client = Client(processes=True)

        # Basic usage
        @task
        def gen_df() -> pd.DataFrame:
            return pd.DataFrame(dict(a=[1]))

        @task
        def show_df(dask_df):
            print(dask_df.compute())

        def add_col(df:pd.DataFrame) -> pd.DataFrame
            return df.assign(b=2)

        with Flow() as f:
            df = gen_df()
            dask_df = transform(df, add_col, schema="*,b:int", engine=client)
            show_df(dask_df)

        # Turning on checkpoint when returning a local dataframe
        with Flow() as f:
            df = gen_df()
            local_df = transform(df, add_col, schema="*,b:int",
                engine=client, as_local=True, checkpoint=True)

        # fsql + transform
        with Flow() as f:
            dfs = fsql("CREATE [[0]] SCHEMA a:int YIELD DATAFRAME AS x",
                checkpoint=False, engine=client)
            dask_df = transform(dfs["x"], add_col, schema="*,b:int",
                engine=client, checkpoint=False)
            fsql('''
                SELECT * FROM df WHERE b<3
                PRINT
            ''', df=dask_df, engine=client)
        ```
    """
    if not isinstance(transformer, Task):
        tn = transformer.__name__ + " (transfomer)"
    else:
        tn = "transform"

    if not isinstance(transformer, Task) and not isinstance(
        kwargs.get("schema", None), Task
    ):
        # construct the transformer at Prefect compile time
        _t = _to_transformer(transformer, kwargs.get("schema", None))

        @task(name=tn, checkpoint=checkpoint)
        def _run_with_func(df: Any, **kwargs):
            kw = dict(kwargs)
            kw.pop("schema", None)
            return fugue.transform(df, _t, **kw)

        return _run_with_func(df, **kwargs)
    else:
        # construct the transformer at Prefect run time

        @task(name=tn, checkpoint=checkpoint)
        def _run(df: Any, func: Any, **kwargs) -> Any:
            return fugue.transform(df, func, **kwargs)

        return _run(df, transformer, **kwargs)


def _truncate_name(name: str) -> str:
    if name is None:
        raise ValueError("task name can't be None")
    if len(name) <= _TASK_NAME_MAX_LEN:
        return name.strip()
    return name[:_TASK_NAME_MAX_LEN].strip() + "..."


def _normalize_yields(yields: Any) -> List[Any]:
    if yields is None:
        return []
    elif isinstance(yields, (list, tuple)):
        return list(yields)
    else:  # single item
        return [yields]
