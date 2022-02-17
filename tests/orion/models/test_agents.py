from uuid import uuid4

import pytest

import pendulum
from sqlalchemy.exc import IntegrityError

from prefect.orion import models, schemas


@pytest.fixture
async def work_queue(session):
    work_queue = await models.work_queues.create_work_queue(
        session=session,
        work_queue=schemas.core.WorkQueue(
            name="My WorkQueue",
            description="All about my work queue",
        ),
    )
    return work_queue


@pytest.fixture
async def agent(session, work_queue):
    agent = await models.agents.create_agent(
        session=session,
        agent=schemas.core.Agent(
            name="My Agent",
            work_queue_id=work_queue.id,
        ),
    )
    return agent


class TestCreateAgent:
    async def test_create_agent_succeeds(self, session, work_queue):
        agent = await models.agents.create_agent(
            session=session,
            agent=schemas.core.Agent(
                name="My Agent",
                work_queue_id=work_queue.id,
            ),
        )
        assert agent.name == "My Agent"
        assert agent.work_queue_id == work_queue.id

    async def test_create_agent_throws_exception_on_name_conflict(
        self,
        session,
        agent,
        work_queue,
    ):
        with pytest.raises(IntegrityError):
            await models.agents.create_agent(
                session=session,
                agent=schemas.core.Agent(name=agent.name, work_queue_id=work_queue.id),
            )


class TestReadAgent:
    async def test_read_agent_by_id(self, session, agent):

        read_agent = await models.agents.read_agent(session=session, agent_id=agent.id)
        assert read_agent.name == agent.name

    async def test_read_agent_by_id_returns_none_if_does_not_exist(self, session):
        assert not await models.agents.read_agent(session=session, agent_id=uuid4())


class TestReadAgents:
    @pytest.fixture
    async def agents(self, session, work_queue):

        agent_1 = await models.agents.create_agent(
            session=session,
            agent=schemas.core.Agent(name="My Agent 1", work_queue_id=work_queue.id),
        )
        agent_2 = await models.agents.create_agent(
            session=session,
            agent=schemas.core.Agent(name="My Agent 2", work_queue_id=work_queue.id),
        )
        await session.commit()
        return [agent_1, agent_2]

    async def test_read_agent(self, agents, session):
        read_agent = await models.agents.read_agents(session=session)
        assert len(read_agent) == len(agents)

    async def test_read_agent_applies_limit(self, agents, session):
        read_agent = await models.agents.read_agents(session=session, limit=1)
        assert {queue.id for queue in read_agent} == {agents[0].id}

    async def test_read_agent_applies_offset(self, agents, session):
        read_agent = await models.agents.read_agents(session=session, offset=1)
        assert {queue.id for queue in read_agent} == {agents[1].id}

    async def test_read_agent_returns_empty_list(self, session):
        read_agent = await models.agents.read_agents(session=session)
        assert len(read_agent) == 0


class TestUpdateAgent:
    async def test_update_agent(self, session, agent, work_queue):
        now = pendulum.now("UTC")
        result = await models.agents.update_agent(
            session=session,
            agent_id=agent.id,
            agent=schemas.core.Agent(
                last_activity_time=now, work_queue_id=work_queue.id
            ),
        )
        assert result

        updated_agent = await models.agents.read_agent(
            session=session, agent_id=agent.id
        )
        assert updated_agent.id == agent.id
        # relevant attributes should be updated
        assert updated_agent.last_activity_time == now
        assert updated_agent.work_queue_id == agent.work_queue_id
        # unset attributes should be ignored
        assert updated_agent.name == agent.name

    async def test_update_agent_returns_false_if_does_not_exist(
        self, session, work_queue
    ):
        result = await models.agents.update_agent(
            session=session,
            agent_id=str(uuid4()),
            agent=schemas.core.Agent(work_queue_id=work_queue.id),
        )
        assert result is False


class TestDeleteAgent:
    async def test_delete_agent(self, session, agent):
        assert await models.agents.delete_agent(session=session, agent_id=agent.id)

        # make sure the agent is deleted
        result = await models.agents.read_agent(session=session, agent_id=agent.id)
        assert result is None

    async def test_delete_agent_returns_false_if_does_not_exist(self, session):
        result = await models.agents.delete_agent(
            session=session, agent_id=str(uuid4())
        )
        assert result is False
