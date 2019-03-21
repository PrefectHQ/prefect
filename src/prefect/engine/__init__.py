from warnings import warn
from prefect import config
import prefect.engine.executors
import prefect.engine.state
import prefect.engine.signals
import prefect.engine.result
import prefect.engine.result_handlers
from prefect.engine.flow_runner import FlowRunner
from prefect.engine.task_runner import TaskRunner
import prefect.engine.cloud


def get_default_executor_class() -> type:
    """
    Returns the `Executor` class specified in
    `prefect.config.engine.executor.default_class`. If the value is a string, it will
    attempt to load the already-imported object. Otherwise, the value is returned.

    Defaults to `SynchronousExecutor` if the string config value can not be loaded
    """
    config_value = config.get_nested("engine.executor.default_class")
    if isinstance(config_value, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(config_value)
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.executors.SynchronousExecutor instead.".format(
                    config_value
                )
            )
            return prefect.engine.executors.SynchronousExecutor
    else:
        return config_value


def get_default_flow_runner_class() -> type:
    """
    Returns the `FlowRunner` class specified in
    `prefect.config.engine.flow_runner.default_class` If the value is a string, it will
    attempt to load the already-imported object. Otherwise, the value is returned.

    Defaults to `FlowRunner` if the string config value can not be loaded
    """
    config_value = config.get_nested("engine.flow_runner.default_class")

    if isinstance(config_value, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(config_value)
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.flow_runner.FlowRunner instead.".format(config_value)
            )
            return prefect.engine.flow_runner.FlowRunner
    else:
        return config_value


def get_default_task_runner_class() -> type:
    """
    Returns the `TaskRunner` class specified in `prefect.config.engine.task_runner.default_class` If the
    value is a string, it will attempt to load the already-imported object. Otherwise, the
    value is returned.

    Defaults to `TaskRunner` if the string config value can not be loaded
    """
    config_value = config.get_nested("engine.task_runner.default_class")

    if isinstance(config_value, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(config_value)
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.task_runner.TaskRunner instead.".format(config_value)
            )
            return prefect.engine.task_runner.TaskRunner
    else:
        return config_value


def get_default_result_handler_class() -> type:
    """
    Returns the `ResultHandler` class specified in `prefect.config.engine.result_handler.default_class` If the
    value is a string, it will attempt to load the already-imported object. Otherwise, the
    value is returned.

    Defaults to `CloudResultHandler` if the string config value can not be loaded
    """
    config_value = config.get_nested("engine.result_handler.default_class")

    if isinstance(config_value, str):
        try:
            return prefect.utilities.serialization.from_qualified_name(config_value)
        except ValueError:
            warn(
                "Could not import {}; using "
                "prefect.engine.cloud.CloudResultHandler instead.".format(config_value)
            )
            return prefect.engine.cloud.CloudResultHandler
    else:
        return config_value
