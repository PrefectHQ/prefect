"""
A service that checks for flow run alerts and sends them.
"""
from typing import List
from prefect.blocks.core import Block
import asyncio

import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.services.loop_service import LoopService


class FlowRunAlerts(LoopService):
    """
    A loop service that checks for flow run alerts that need to be sent.

    Alerts are queued, and this service pulls them off the queue and actually
    sends the notification.
    """

    batch_size: int = 10

    # check queue every 4 seconds
    # note: a tight loop is executed until the queue is exhausted
    loop_seconds: int = 4

    @inject_db
    async def run_once(self, db: OrionDBInterface):
        session = await db.session()

        async with session:
            async with session.begin():
                while True:
                    alerts = await db.get_flow_run_alerts_from_queue(
                        session=session,
                        limit=self.batch_size,
                    )
                    self.logger.debug(f"Got {len(alerts)} alerts from queue.")

                    # if no alerts were found, exit the tight loop and sleep
                    if not alerts:
                        break

                    await self.send_flow_run_alerts(
                        session=session, db=db, alerts=alerts
                    )

    @inject_db
    async def send_flow_run_alerts(
        self, session: sa.orm.session, db: OrionDBInterface, alerts: List
    ):
        for alert in alerts:
            try:
                orm_block_document = await session.get(
                    db.BlockDocument, alert.block_document_id
                )
                if orm_block_document is None:
                    continue
                block = Block.from_block_document(
                    await schemas.core.BlockDocument.from_orm_model(
                        session=session, orm_block_document=orm_block_document
                    )
                )

                message_template = (
                    alert.flow_run_alert_policy_message_template
                    or models.flow_run_alert_policies.DEFAULT_MESSAGE_TEMPLATE
                )
                message = message_template.format(
                    **{k: alert[k] for k in schemas.core.FLOW_RUN_ALERT_TEMPLATE_KWARGS}
                )
                await block.notify(body=message)

                self.logger.debug(
                    f"Successfully sent alert for flow run {alert.flow_run_id} "
                    f"from policy {alert.flow_run_alert_policy_id}"
                )

            except Exception as exc:
                self.logger.error(f"Error sending alert: {exc}")


if __name__ == "__main__":
    asyncio.run(FlowRunAlerts().start())
