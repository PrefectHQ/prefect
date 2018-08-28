# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
Prefect Executors encapsulate the logic for how Tasks are run.

For example, decisions about multi-threading or whether to use parallelism
are handled by choice of Executor.
"""
from warnings import warn as _warn
from importlib import import_module as _import_module

import prefect as _prefect
from prefect.engine.executors.base import Executor
from prefect.engine.executors.local import LocalExecutor
from prefect.engine.executors.dask import DaskExecutor
from prefect.engine.executors.dask import SynchronousExecutor

try:
    cfg_exec = _prefect.config.engine.executor
    *module, cls_name = cfg_exec.split(".")
    module = _import_module(".".join(module))
    DEFAULT_EXECUTOR = getattr(module, cls_name)()
except:
    _warn(
        "Could not import {}, using prefect.engine.executors.LocalExecutor instead.".format(
            _prefect.config.engine.executor
        )
    )
    DEFAULT_EXECUTOR = LocalExecutor()
