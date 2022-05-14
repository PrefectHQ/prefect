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
                    alerts = await self.get_queued_flow_run_alerts(
                        session=session, db=db, n_alerts=self.batch_size
                    )

                    # if no alerts were found, exit the tight loop and sleep
                    if not alerts:
                        break

                    await self.send_flow_run_alerts(
                        session=session, db=db, alerts=alerts
                    )

            self.logger.info(f"Finished sending flow run alerts.")

    @inject_db
    async def get_queued_flow_run_alerts(
        self,
        session: sa.orm.session,
        db: OrionDBInterface,
        n_alerts: int = 1,
    ):
        queued_alerts = (
            sa.delete(db.FlowRunAlertQueue)
            .returning(
                db.FlowRunAlertQueue.flow_run_alert_policy_id,
                db.FlowRunAlertQueue.flow_run_state_id,
            )
            .where(
                db.FlowRunAlertQueue.id.in_(
                    sa.select(db.FlowRunAlertQueue.id)
                    .select_from(db.FlowRunAlertQueue)
                    .order_by(db.FlowRunAlertQueue.updated)
                    .limit(n_alerts)
                    .with_for_update(skip_locked=True)
                )
            )
            .cte("queued_alerts")
        )

        alert_details_stmt = (
            sa.select(
                db.FlowRunAlertPolicy.id.label("flow_run_alert_policy_id"),
                db.FlowRunAlertPolicy.name.label("flow_run_alert_policy_name"),
                db.FlowRunAlertPolicy.message_template.label(
                    "flow_run_alert_policy_message_template"
                ),
                db.FlowRunAlertPolicy.block_document_id,
                db.Flow.id.label("flow_id"),
                db.Flow.name.label("flow_name"),
                db.FlowRun.id.label("flow_run_id"),
                db.FlowRun.name.label("flow_run_name"),
                db.FlowRun.parameters.label("flow_run_parameters"),
                db.FlowRunState.type.label("flow_run_state_type"),
                db.FlowRunState.name.label("flow_run_state_name"),
                db.FlowRunState.timestamp.label("flow_run_state_timestamp"),
                db.FlowRunState.message.label("flow_run_state_message"),
            )
            .select_from(queued_alerts)
            .join(
                db.FlowRunAlertPolicy,
                queued_alerts.c.flow_run_alert_policy_id == db.FlowRunAlertPolicy.id,
            )
            .join(
                db.FlowRunState,
                queued_alerts.c.flow_run_state_id == db.FlowRunState.id,
            )
            .join(
                db.FlowRun,
                db.FlowRunState.flow_run_id == db.FlowRun.id,
            )
            .join(
                db.Flow,
                db.FlowRun.flow_id == db.Flow.id,
            )
        )

        result = await session.execute(alert_details_stmt)
        alerts = result.fetchall()
        self.logger.debug(f"Got {len(alerts)} alerts from queue.")
        return alerts

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
                    **{
                        k: alert[k]
                        for k in models.flow_run_alert_policies.TEMPLATE_KWARGS
                    }
                )
                await block.send(message)

                self.logger.debug(
                    f"Successfully sent alert for flow run {alert.flow_run_id}"
                )

            except Exception as exc:
                self.logger.error(f"Error sending alert: {exc}")


if __name__ == "__main__":
    asyncio.run(FlowRunAlerts().start())
