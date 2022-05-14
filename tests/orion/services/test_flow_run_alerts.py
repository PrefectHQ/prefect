import pytest

from prefect.blocks.notifications import DebugPrintNotification
from prefect.orion import models, schemas


@pytest.fixture(autouse=True)
async def notifier_block(orion_client):

    block = DebugPrintNotification()
    schema = await orion_client.read_block_schema_by_checksum(
        block.calculate_schema_checksum()
    )

    return await orion_client.create_block_document(
        block.to_block_document(
            name="Debug Print Notification", block_schema_id=schema.id
        )
    )


@pytest.fixture
async def completed_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=["Completed"],
            tags=[],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy


@pytest.fixture
async def completed_etl_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=["Completed"],
            tags=["ETL"],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy


@pytest.fixture
async def failed_policy(session, notifier_block):
    policy = await models.flow_run_alert_policies.create_flow_run_alert_policy(
        session=session,
        flow_run_alert_policy=schemas.core.FlowRunAlertPolicy(
            name="My Success Policy",
            state_names=["Failed"],
            tags=[],
            block_document_id=notifier_block.id,
        ),
    )
    await session.commit()
    return policy
