# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
from warnings import warn

import prefect.engine.executors
import prefect.engine.state
import prefect.engine.signals
import prefect.engine.cloud_runners
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.task_runner import TaskRunner


def get_default_executor_class() -> type:
    """
    Returns the `Executor` class specified in `prefect.config.engine.executor`

    Defaults to `SynchronousExecutor` if the config value can not be loaded
    """
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


def get_default_flow_runner_class() -> type:
    """
    Returns the `FlowRunner` class specified in `prefect.config.engine.flow_runner`

    Defaults to `FlowRunner` if the config value can not be loaded
    """

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


def get_default_task_runner_class() -> type:
    """
    Returns the `TaskRunner` class specified in `prefect.config.engine.task_runner`

    Defaults to `TaskRunner` if the config value can not be loaded
    """

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
