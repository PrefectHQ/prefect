import time
from unittest.mock import MagicMock, Mock
from pandas import DataFrame

import pytest

import prefect
from prefect.tasks.azure import DatafactoryCreate, PipelineCreate, PipelineRun
from prefect.utilities.configuration import set_temporary_config


class MockFactory():
    def __init__(self, **kwargs):
        self.provisioning_state = "Queued"
        self.status = "Queued"
        time.sleep(0.5)
        self.provisioning_state = "Succeeded"
        self.status = "Succeeded"

class MockClient():

    def __init__(self, *args, **kwargs):
        pass

    @property
    def factories(self):
        return MagicMock(create_or_update=lambda *args: MockFactory())

    @property
    def pipelines(self):
        return MagicMock(create_or_update=lambda *args: MockFactory())

    @property
    def pipeline_runs(self):
        return MagicMock(create_or_update=lambda *args: MockFactory(), get=lambda *args: MagicMock(status="Succeeded"))

    @property
    def activity_runs(self):
        return MagicMock(query_by_pipeline_run=lambda *args: {"result": "success"})


class TestDatafactoryCreate:
    def test_initialization(self):
        task = DatafactoryCreate()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = DatafactoryCreate(
            datafactory_name="df_name",
            resource_group_name="rg_name"
        )
        assert task.datafactory_name == "df_name"
        assert task.resource_group_name == "rg_name"

    @pytest.mark.parametrize("required_arg", ["datafactory_name", "resource_group_name"])
    def test_raises_if_required_args_not_eventually_provided(self, required_arg):
        task = DatafactoryCreate()
        required_args = {"datafactory_name": "name", "resource_group_name": "name"}
        required_args.pop(required_arg)
        with pytest.raises(ValueError, match="must be specified"):
            task.run(**required_args)

    def test_raises_if_required_args_empty_string(self):
        task = DatafactoryCreate()
        required_args = {"datafactory_name": "", "resource_group_name": ""}
        with pytest.raises(ValueError, match="must be specified"):
            task.run(**required_args)

    def test_run(self, monkeypatch):
        datafactory = MagicMock(DataFactoryManagementClient=MockClient)
        monkeypatch.setattr("prefect.tasks.azure.datafactory.azure.mgmt.datafactory", datafactory)
        task = DatafactoryCreate()
        result = task.run(datafactory_name="df_name", resource_group_name="rg_name")
        assert result == "df_name"


class TestPipelineCreate:
    def test_initialization(self):
        task = PipelineCreate()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = PipelineCreate(
            datafactory_name="df_name",
            resource_group_name="rg_name",
            pipeline_name="p_name"
        )
        assert task.datafactory_name == "df_name"
        assert task.resource_group_name == "rg_name"
        assert task.pipeline_name == "p_name"

    @pytest.mark.parametrize("required_arg", ["datafactory_name", "resource_group_name", "pipeline_name", "activities"])
    def test_raises_if_required_args_not_eventually_provided(self, required_arg):
        task = PipelineCreate()
        required_args = {"datafactory_name": "name", "resource_group_name": "name", "pipeline_name": "name", "activities": []}
        required_args.pop(required_arg)
        with pytest.raises(ValueError, match="must be specified"):
            task.run(**required_args)

    def test_raises_if_required_args_empty_string(self):
        task = PipelineCreate()
        required_args = {"datafactory_name": "", "resource_group_name": "", "pipeline_name": ""}
        with pytest.raises(ValueError, match="must be specified"):
            task.run(**required_args)

    def test_run(self, monkeypatch):
        datafactory = MagicMock(DataFactoryManagementClient=MockClient)
        monkeypatch.setattr("prefect.tasks.azure.datafactory.azure.mgmt.datafactory", datafactory)
        task = PipelineCreate()
        result = task.run(datafactory_name="df_name", resource_group_name="rg_name", pipeline_name="p_name", activities=["activity"])
        assert result == "p_name"


class TestPipelineRun:
    def test_initialization(self):
        task = PipelineRun()
        assert task.azure_credentials_secret == "AZ_CREDENTIALS"

    def test_initialization_passes_to_task_constructor(self):
        task = PipelineRun(
            datafactory_name="df_name",
            resource_group_name="rg_name",
            pipeline_name="p_name"
        )
        assert task.datafactory_name == "df_name"
        assert task.resource_group_name == "rg_name"
        assert task.pipeline_name == "p_name"

    @pytest.mark.parametrize("required_arg", ["datafactory_name", "resource_group_name", "pipeline_name"])
    def test_raises_if_required_args_not_eventually_provided(self, required_arg):
        task = PipelineRun()
        required_args = {"datafactory_name": "name", "resource_group_name": "name", "pipeline_name": "name"}
        required_args.pop(required_arg)
        with pytest.raises(ValueError, match="must be specified"):
            task.run(**required_args)

    def test_raises_if_required_args_empty_string(self):
        task = PipelineRun()
        required_args = {"datafactory_name": "", "resource_group_name": "", "pipeline_name": ""}
        with pytest.raises(ValueError, match="must be specified"):
            task.run(**required_args)

    def test_run(self, monkeypatch):
        datafactory = MagicMock(DataFactoryManagementClient=MockClient)
        monkeypatch.setattr("prefect.tasks.azure.datafactory.azure.mgmt.datafactory", datafactory)
        task = PipelineRun()
        result = task.run(datafactory_name="df_name", resource_group_name="rg_name", pipeline_name="p_name")
        assert result == {"result": "success"}