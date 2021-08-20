from uuid import uuid4

import pytest
import sqlalchemy as sa

from prefect.orion import models, schemas


class TestCreateDeployment:
    async def test_create_deployment_succeeds(self, session, flow):
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="My Deployment", flow_id=flow.id),
        )
        assert deployment.name == "My Deployment"
        assert deployment.flow_id == flow.id

    async def test_create_deployment_raises_if_id_exists(self, session, flow):
        deployment_id = uuid4()
        await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(
                id=deployment_id, flow_id=flow.id, name="My Deployment"
            ),
        )
        with pytest.raises(sa.exc.IntegrityError):
            await models.deployments.create_deployment(
                session=session,
                deployment=schemas.core.Deployment(
                    id=deployment_id, flow_id=flow.id, name="My Deployment"
                ),
            )


class TestReadDeployment:
    async def test_read_deployment(self, session, flow):
        # create a deployment to read
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="My Deployment", flow_id=flow.id),
        )
        assert deployment.name == "My Deployment"

        read_deployment = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        assert deployment.id == read_deployment.id
        assert deployment.name == read_deployment.name

    async def test_read_deployment_returns_none_if_does_not_exist(self, session):
        result = await models.deployments.read_deployment(
            session=session, deployment_id=str(uuid4())
        )
        assert result is None


class TestReadDeployments:
    @pytest.fixture
    async def deployments(self, session, flow):
        deployment_1 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="My Deployment-1", flow_id=flow.id),
        )
        deployment_2 = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="My Deployment-2", flow_id=flow.id),
        )
        return [deployment_1, deployment_2]

    async def test_read_deployments(self, deployments, session):
        read_deployments = await models.deployments.read_deployments(session=session)
        assert len(read_deployments) == len(deployments)

    async def test_read_deployments_applies_limit(self, deployments, session):
        read_deployments = await models.deployments.read_deployments(
            session=session, limit=1
        )
        assert len(read_deployments) == 1

    async def test_read_deployments_applies_offset(self, deployments, session):
        read_deployments = await models.deployments.read_deployments(
            session=session, offset=1
        )

    async def test_read_deployments_returns_empty_list(self, session):
        read_deployments = await models.deployments.read_deployments(session=session)
        assert len(read_deployments) == 0


class TestDeleteDeployment:
    async def test_delete_deployment(self, session, flow):
        # create a deployment to delete
        deployment = await models.deployments.create_deployment(
            session=session,
            deployment=schemas.core.Deployment(name="My Deployment", flow_id=flow.id),
        )
        assert deployment.name == "My Deployment"

        assert await models.deployments.delete_deployment(
            session=session, deployment_id=deployment.id
        )

        # make sure the deployment is deleted
        result = await models.deployments.read_deployment(
            session=session, deployment_id=deployment.id
        )
        assert result is None

    async def test_delete_deployment_returns_false_if_does_not_exist(self, session):
        result = await models.deployments.delete_deployment(
            session=session, deployment_id=str(uuid4())
        )
        assert result is False
