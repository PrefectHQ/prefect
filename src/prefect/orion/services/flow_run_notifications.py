"""
A service that checks for flow run notifications and sends them.
"""
import asyncio
from typing import List

import sqlalchemy as sa

from prefect.blocks.core import Block
from prefect.orion import models, schemas
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.services.loop_service import LoopService


class FlowRunNotifications(LoopService):
    """
    A loop service that checks for flow run notifications that need to be sent.

    Notifications are queued, and this service pulls them off the queue and
    actually sends the notification.
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
                    notifications = await db.get_flow_run_notifications_from_queue(
                        session=session,
                        limit=self.batch_size,
                    )
                    self.logger.debug(
                        f"Got {len(notifications)} notifications from queue."
                    )

                    # if no notifications were found, exit the tight loop and sleep
                    if not notifications:
                        break

                    await self.send_flow_run_notifications(
                        session=session, db=db, notifications=notifications
                    )

    @inject_db
    async def send_flow_run_notifications(
        self, session: sa.orm.session, db: OrionDBInterface, notifications: List
    ):
        for notification in notifications:
            try:
                orm_block_document = await session.get(
                    db.BlockDocument, notification.block_document_id
                )
                if orm_block_document is None:
                    self.logger.error(
                        f"Missing block document {notification.block_document_id} "
                        f"from policy {notification.flow_run_notification_policy_id}"
                    )
                    continue
                block = Block._from_block_document(
                    await schemas.core.BlockDocument.from_orm_model(
                        session=session,
                        orm_block_document=orm_block_document,
                        include_secrets=True,
                    )
                )

                message_template = (
                    notification.flow_run_notification_policy_message_template
                    or models.flow_run_notification_policies.DEFAULT_MESSAGE_TEMPLATE
                )
                message = message_template.format(
                    **{
                        k: notification[k]
                        for k in schemas.core.FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS
                    }
                )
                await block.notify(
                    subject="Prefect flow run notification",
                    body=message,
                )

                self.logger.debug(
                    f"Successfully sent notification for flow run {notification.flow_run_id} "
                    f"from policy {notification.flow_run_notification_policy_id}"
                )

            except Exception:
                self.logger.error(
                    f"Error sending notification for policy {notification.flow_run_notification_policy_id} "
                    f"on flow run {notification.flow_run_id}",
                    exc_info=True,
                )


if __name__ == "__main__":
    asyncio.run(FlowRunNotifications().start())
