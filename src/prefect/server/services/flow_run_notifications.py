"""
A service that checks for flow run notifications and sends them.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

import sqlalchemy as sa

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.server.database.dependencies import db_injector
from prefect.server.database.query_components import FlowRunNotificationsFromQueue
from prefect.server.services.base import LoopService
from prefect.settings import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.utilities import urls


class FlowRunNotifications(LoopService):
    """
    Sends queued flow run notifications.
    """

    # check queue every 4 seconds
    # note: a tight loop is executed until the queue is exhausted
    loop_seconds: float = 4

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.flow_run_notifications

    @db_injector
    async def run_once(self, db: PrefectDBInterface) -> None:
        while True:
            async with db.session_context(begin_transaction=True) as session:
                # Drain the queue one entry at a time, because if a transient
                # database error happens while sending a notification, the whole
                # transaction will be rolled back, which effectively re-queues any
                # notifications that we pulled here.  If we drain in batches larger
                # than 1, we risk double-sending earlier notifications when a
                # transient error occurs.
                notifications = await db.queries.get_flow_run_notifications_from_queue(
                    session=session, limit=1
                )
                self.logger.debug(f"Got {len(notifications)} notifications from queue.")

                # if no notifications were found, exit the tight loop and sleep
                if not notifications:
                    break

                # all retrieved notifications are deleted, assert that we only got one
                # since we only send the first notification returned
                assert len(notifications) == 1, (
                    "Expected one notification; query limit not respected."
                )

                try:
                    await self.send_flow_run_notification(
                        session=session, db=db, notification=notifications[0]
                    )
                finally:
                    connection = await session.connection()
                    if connection.invalidated:
                        # If the connection was invalidated due to an error that we
                        # handled in _send_flow_run_notification, we'll need to
                        # rollback the session in order to synchronize it with the
                        # reality of the underlying connection before we can proceed
                        # with more iterations of the loop.  This may happen due to
                        # transient database connection errors, but will _not_
                        # happen due to an calling a third-party service to send a
                        # notification.
                        await session.rollback()
                        assert not connection.invalidated

    async def send_flow_run_notification(
        self,
        db: PrefectDBInterface,
        session: sa.orm.session,
        notification: FlowRunNotificationsFromQueue,
    ) -> None:
        try:
            orm_block_document = await session.get(
                db.BlockDocument, notification.block_document_id
            )
            if orm_block_document is None:
                self.logger.error(
                    f"Missing block document {notification.block_document_id} "
                    f"from policy {notification.flow_run_notification_policy_id}"
                )
                return

            from prefect.blocks.core import Block

            block = Block._from_block_document(
                await schemas.core.BlockDocument.from_orm_model(
                    session=session,
                    orm_block_document=orm_block_document,
                    include_secrets=True,
                )
            )

            message = self.construct_notification_message(notification=notification)
            if TYPE_CHECKING:
                from prefect.blocks.abstract import NotificationBlock

                assert isinstance(block, NotificationBlock)
            await block.notify(
                subject="Prefect flow run notification",
                body=message,
            )

            self.logger.debug(
                "Successfully sent notification for flow run"
                f" {notification.flow_run_id} from policy"
                f" {notification.flow_run_notification_policy_id}"
            )

        except Exception:
            self.logger.error(
                (
                    "Error sending notification for policy"
                    f" {notification.flow_run_notification_policy_id} on flow run"
                    f" {notification.flow_run_id}"
                ),
                exc_info=True,
            )

    def construct_notification_message(
        self, notification: FlowRunNotificationsFromQueue
    ) -> str:
        """
        Construct the message for a flow run notification, including
        templating any variables.
        """
        message_template = (
            notification.flow_run_notification_policy_message_template
            or models.flow_run_notification_policies.DEFAULT_MESSAGE_TEMPLATE
        )

        # create a dict from the sqlalchemy object for templating
        notification_dict: dict[str, Any] = dict(notification._mapping)
        # add the flow run url to the info
        notification_dict["flow_run_url"] = self.get_ui_url_for_flow_run_id(
            flow_run_id=notification_dict["flow_run_id"]
        )

        message = message_template.format(
            **{
                k: notification_dict[k]
                for k in schemas.core.FLOW_RUN_NOTIFICATION_TEMPLATE_KWARGS
            }
        )
        return message

    def get_ui_url_for_flow_run_id(self, flow_run_id: UUID) -> str | None:
        """
        Returns a link to the flow run view of the given flow run id.

        Args:
            flow_run_id: the flow run id.
        """
        return urls.url_for(
            "flow-run",
            obj_id=flow_run_id,
            default_base_url="http://ephemeral-prefect/api",
        )


if __name__ == "__main__":
    asyncio.run(FlowRunNotifications(handle_signals=True).start())
