# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
from warnings import warn

import prefect.engine.cloud
import prefect.engine.executors
import prefect.engine.state
import prefect.engine.signals
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.task_runner import TaskRunner


def get_default_executor_class() -> type:
    """
    Returns the `Executor` class specified in `prefect.config.engine.executor`. If the
    value is a string, it will attempt to load the already-imported object. Otherwise, the
    value is returned.

    Defaults to `SynchronousExecutor` if the string config value can not be loaded
    """
    if isinstance(prefect.config.engine.executor, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(
                prefect.config.engine.executor
            )
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.executors.SynchronousExecutor instead.".format(
                    prefect.config.engine.executor
                )
            )
            return prefect.engine.executors.SynchronousExecutor
    else:
        return prefect.config.engine.executor


def get_default_flow_runner_class() -> type:
    """
    Returns the `FlowRunner` class specified in `prefect.config.engine.flow_runner` If the
    value is a string, it will attempt to load the already-imported object. Otherwise, the
    value is returned.

    Defaults to `FlowRunner` if the string config value can not be loaded
    """

    if isinstance(prefect.config.engine.flow_runner, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(
                prefect.config.engine.flow_runner
            )
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.flow_runner.FlowRunner instead.".format(
                    prefect.config.engine.flow_runner
                )
            )
            return prefect.engine.flow_runner.FlowRunner
    else:
        return prefect.config.engine.flow_runner


def get_default_task_runner_class() -> type:
    """
    Returns the `TaskRunner` class specified in `prefect.config.engine.task_runner` If the
    value is a string, it will attempt to load the already-imported object. Otherwise, the
    value is returned.

    Defaults to `TaskRunner` if the string config value can not be loaded
    """

    if isinstance(prefect.config.engine.task_runner, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(
                prefect.config.engine.task_runner
            )
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.task_runner.TaskRunner instead.".format(
                    prefect.config.engine.task_runner
                )
            )
            return prefect.engine.task_runner.TaskRunner
    else:
        return prefect.config.engine.task_runner
