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


def transform(df: Any, transformer: Any, checkpoint: bool = False, **kwargs) -> Any:
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
