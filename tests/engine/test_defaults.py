import pytest

from prefect import engine, executors, utilities


def test_default_executor():
    assert engine.get_default_executor_class() is executors.LocalExecutor


def test_default_executor_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"engine.executor.default_class": "prefect.executors.LocalDaskExecutor"}
    ):
        assert engine.get_default_executor_class() is executors.LocalDaskExecutor


def test_default_executor_responds_to_config_object():
    with utilities.configuration.set_temporary_config(
        {"engine.executor.default_class": executors.LocalDaskExecutor}
    ):
        assert engine.get_default_executor_class() is executors.LocalDaskExecutor


def test_default_executor_with_bad_config():
    with utilities.configuration.set_temporary_config(
        {"engine.executor.default_class": "prefect.engine.bad import path"}
    ):
        with pytest.warns(UserWarning):
            assert engine.get_default_executor_class() is executors.LocalExecutor


def test_default_flow_runner():
    assert engine.get_default_flow_runner_class() is engine.flow_runner.FlowRunner


def test_default_flow_runner_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"engine.flow_runner.default_class": "prefect.engine.cloud.CloudFlowRunner"}
    ):
        assert engine.get_default_flow_runner_class() is engine.cloud.CloudFlowRunner


def test_default_flow_runner_responds_to_config_object():
    with utilities.configuration.set_temporary_config(
        {"engine.flow_runner.default_class": engine.cloud.CloudFlowRunner}
    ):
        assert engine.get_default_flow_runner_class() is engine.cloud.CloudFlowRunner


def test_default_flow_runner_with_bad_config():
    with utilities.configuration.set_temporary_config(
        {"engine.flow_runner.default_class": "prefect.engine. bad import path"}
    ):
        with pytest.warns(UserWarning):
            assert (
                engine.get_default_flow_runner_class() is engine.flow_runner.FlowRunner
            )


def test_default_task_runner():
    assert engine.get_default_task_runner_class() is engine.task_runner.TaskRunner


def test_default_task_runner_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"engine.task_runner.default_class": "prefect.engine.cloud.CloudTaskRunner"}
    ):
        assert engine.get_default_task_runner_class() is engine.cloud.CloudTaskRunner


def test_default_task_runner_responds_to_config_object():
    with utilities.configuration.set_temporary_config(
        {"engine.task_runner.default_class": engine.cloud.CloudTaskRunner}
    ):
        assert engine.get_default_task_runner_class() is engine.cloud.CloudTaskRunner


def test_default_task_runner_with_bad_config():
    with utilities.configuration.set_temporary_config(
        {"engine.task_runner.default_class": "prefect.engine. bad import path"}
    ):
        with pytest.warns(UserWarning):
            assert (
                engine.get_default_task_runner_class() is engine.task_runner.TaskRunner
            )
