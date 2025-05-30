import pytest
import asyncio
import datetime
from unittest import mock

from prefect import flow
from prefect._experimental.sla.objects import TimeToCompletionSla, LatenessSla
from prefect.deployments.runner import RunnerDeployment
from prefect.client.orchestration import PrefectClient


@pytest.fixture
def sla_object_1():
    return TimeToCompletionSla(timedelta=datetime.timedelta(hours=1))


@pytest.fixture
def sla_object_2():
    return LatenessSla(timedelta=datetime.timedelta(minutes=30))


@pytest.fixture
def sla_override_object():
    return TimeToCompletionSla(timedelta=datetime.timedelta(hours=2))


class TestFlowToDeploymentSLA:
    def test_to_deployment_with_single_sla(self, sla_object_1):
        @flow(sla=sla_object_1)
        def my_flow_single_sla():
            pass

        deployment = my_flow_single_sla.to_deployment(name="test-deploy-single-sla")
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla == [sla_object_1]

    def test_to_deployment_with_list_sla(self, sla_object_1, sla_object_2):
        @flow(sla=[sla_object_1, sla_object_2])
        def my_flow_list_sla():
            pass

        deployment = my_flow_list_sla.to_deployment(name="test-deploy-list-sla")
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla == [sla_object_1, sla_object_2]

    def test_to_deployment_with_no_sla(self):
        @flow
        def my_flow_no_sla():
            pass

        deployment = my_flow_no_sla.to_deployment(name="test-deploy-no-sla")
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla is None

    def test_to_deployment_override_sla(self, sla_object_1, sla_override_object):
        @flow(sla=sla_object_1)
        def my_flow_override_sla():
            pass

        deployment = my_flow_override_sla.to_deployment(
            name="test-deploy-override-sla", _sla=sla_override_object
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla == [sla_override_object]

    def test_to_deployment_override_with_list_sla(
        self, sla_object_1, sla_object_2, sla_override_object
    ):
        @flow(sla=sla_object_1)
        def my_flow_override_list_sla():
            pass

        deployment = my_flow_override_list_sla.to_deployment(
            name="test-deploy-override-list-sla", _sla=[sla_override_object, sla_object_2]
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla == [sla_override_object, sla_object_2]

    def test_to_deployment_clear_sla_with_none_override(self, sla_object_1):
        @flow(sla=sla_object_1)
        def my_flow_clear_sla():
            pass

        deployment = my_flow_clear_sla.to_deployment(
            name="test-deploy-clear-sla", _sla=None
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla is None

    async def test_ato_deployment_with_single_sla(self, sla_object_1):
        @flow(sla=sla_object_1)
        async def my_async_flow_single_sla():
            pass

        deployment = await my_async_flow_single_sla.ato_deployment(name="test-async-deploy-single-sla")
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla == [sla_object_1]

    async def test_ato_deployment_override_sla(self, sla_object_1, sla_override_object):
        @flow(sla=sla_object_1)
        async def my_async_flow_override_sla():
            pass

        deployment = await my_async_flow_override_sla.ato_deployment(
            name="test-async-deploy-override-sla", _sla=sla_override_object
        )
        assert isinstance(deployment, RunnerDeployment)
        assert deployment._sla == [sla_override_object]


@pytest.mark.usefixtures("mock_client_deploy")
class TestFlowDeploySLA:
    @pytest.fixture
    def mock_client_deploy(self, monkeypatch):
        """Mocks prefect.deployments.runner.deploy to inspect its arguments"""
        mock_deploy_fn = mock.AsyncMock(return_value=[mock.MagicMock()]) # Returns list of deployment IDs
        monkeypatch.setattr("prefect.deployments.runner.deploy", mock_deploy_fn)
        return mock_deploy_fn
    
    async def test_deploy_with_flow_sla(self, mock_client_deploy, sla_object_1, work_pool):
        @flow(sla=sla_object_1)
        def my_flow_deploy_sla():
            pass

        await my_flow_deploy_sla.deploy(
            name="test-live-deploy-flow-sla",
            work_pool_name=work_pool.name,
            image="test-image"
        )

        mock_client_deploy.assert_called_once()
        deployment_obj = mock_client_deploy.call_args[0][0]
        assert isinstance(deployment_obj, RunnerDeployment)
        assert deployment_obj._sla == [sla_object_1]

    async def test_deploy_override_sla(self, mock_client_deploy, sla_object_1, sla_override_object, work_pool):
        @flow(sla=sla_object_1)
        def my_flow_deploy_override_sla():
            pass

        await my_flow_deploy_override_sla.deploy(
            name="test-live-deploy-override-sla",
            work_pool_name=work_pool.name,
            image="test-image",
            _sla=sla_override_object,
        )

        mock_client_deploy.assert_called_once()
        deployment_obj = mock_client_deploy.call_args[0][0]
        assert isinstance(deployment_obj, RunnerDeployment)
        assert deployment_obj._sla == [sla_override_object]
        
    async def test_deploy_clear_sla_with_none_override(self, mock_client_deploy, sla_object_1, work_pool):
        @flow(sla=sla_object_1)
        def my_flow_deploy_clear_sla():
            pass

        await my_flow_deploy_clear_sla.deploy(
            name="test-live-deploy-clear-sla",
            work_pool_name=work_pool.name,
            image="test-image",
            _sla=None,
        )

        mock_client_deploy.assert_called_once()
        deployment_obj = mock_client_deploy.call_args[0][0]
        assert isinstance(deployment_obj, RunnerDeployment)
        assert deployment_obj._sla is None

    async def test_deploy_with_no_flow_sla_and_no_override(self, mock_client_deploy, work_pool):
        @flow
        def my_flow_deploy_no_sla():
            pass

        await my_flow_deploy_no_sla.deploy(
            name="test-live-deploy-no-sla",
            work_pool_name=work_pool.name,
            image="test-image",
        ) # _sla defaults to None

        mock_client_deploy.assert_called_once()
        deployment_obj = mock_client_deploy.call_args[0][0]
        assert isinstance(deployment_obj, RunnerDeployment)
        assert deployment_obj._sla is None

    async def test_deploy_with_list_sla_override(self, mock_client_deploy, sla_object_1, sla_object_2, sla_override_object, work_pool):
        @flow(sla=sla_object_1)
        def my_flow_deploy_list_override_sla():
            pass

        override_sla_list = [sla_override_object, sla_object_2]
        await my_flow_deploy_list_override_sla.deploy(
            name="test-live-deploy-list-override-sla",
            work_pool_name=work_pool.name,
            image="test-image",
            _sla=override_sla_list,
        )

        mock_client_deploy.assert_called_once()
        deployment_obj = mock_client_deploy.call_args[0][0]
        assert isinstance(deployment_obj, RunnerDeployment)
        assert deployment_obj._sla == override_sla_list
