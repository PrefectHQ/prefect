from warnings import warn as _warn
from importlib import import_module as _import_module

import prefect as _prefect
from prefect.engine.executors.base import Executor
from prefect.engine.executors.local import LocalExecutor
from prefect.engine.executors.dask import DaskExecutor
from prefect.engine.executors.distributed import DistributedExecutor

try:
    cfg_exec = _prefect.config.engine.executor
    *module, cls_name = cfg_exec.split(".")
    module = _import_module(".".join(module))
    DEFAULT_EXECUTOR = getattr(module, cls_name)()
except:
    _warn(
        "Could not import {}, using prefect.engine.executors.LocalExecutor instead.".format(
            cfg_exec
        )
    )
    DEFAULT_EXECUTOR = LocalExecutor()
