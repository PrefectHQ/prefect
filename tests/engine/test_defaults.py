import pytest
from prefect import engine, utilities


def test_default_executor():
    assert engine.get_default_executor_class() is engine.executors.SynchronousExecutor


def test_default_executor_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"engine.executor": "prefect.engine.executors.LocalExecutor"}
    ):
        assert engine.get_default_executor_class() is engine.executors.LocalExecutor


def test_default_executor_with_bad_config():
    with utilities.configuration.set_temporary_config(
        {"engine.executor": "prefect.engine.bad import path"}
    ):
        with pytest.warns(UserWarning):
            assert (
                engine.get_default_executor_class()
                is engine.executors.SynchronousExecutor
            )


def test_default_flow_runner():
    assert engine.get_default_flow_runner_class() is engine.flow_runner.FlowRunner


def test_default_flow_runner_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"engine.flow_runner": "prefect.engine.cloud_runners.CloudFlowRunner"}
    ):
        assert (
            engine.get_default_flow_runner_class()
            is engine.cloud_runners.CloudFlowRunner
        )


def test_default_flow_runner_with_bad_config():
    with utilities.configuration.set_temporary_config(
        {"engine.flow_runner": "prefect.engine. bad import path"}
    ):
        with pytest.warns(UserWarning):
            assert (
                engine.get_default_flow_runner_class() is engine.flow_runner.FlowRunner
            )


def test_default_task_runner():
    assert engine.get_default_task_runner_class() is engine.task_runner.TaskRunner


def test_default_task_runner_responds_to_config():
    with utilities.configuration.set_temporary_config(
        {"engine.task_runner": "prefect.engine.cloud_runners.CloudTaskRunner"}
    ):
        assert (
            engine.get_default_task_runner_class()
            is engine.cloud_runners.CloudTaskRunner
        )


def test_default_task_runner_with_bad_config():
    with utilities.configuration.set_temporary_config(
        {"engine.task_runner": "prefect.engine. bad import path"}
    ):
        with pytest.warns(UserWarning):
            assert (
                engine.get_default_task_runner_class() is engine.task_runner.TaskRunner
            )
